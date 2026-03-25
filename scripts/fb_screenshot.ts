#!/usr/bin/env npx tsx
/**
 * Facebook 帖子截图脚本
 * 用法: npx tsx fb_screenshot.ts <POST_URL> [OUTPUT_PATH]
 * 示例: npx tsx fb_screenshot.ts "https://www.facebook.com/groups/xxx/posts/yyy" "./screenshots/post.png"
 */

import { chromium, Browser, Page } from 'playwright';
import path from 'path';
import fs from 'fs';

const DEFAULT_VIEWPORT = { width: 1280, height: 720 };
const DEFAULT_OUTPUT = './fb_screenshot.png';
const SCROLL_DELAY_MS = 800;
const ELEMENT_WAIT_MS = 2000;

// 安全配置
const ALLOWED_DOMAINS = ['facebook.com', 'www.facebook.com', 'm.facebook.com', 'mbasic.facebook.com'];
const WORKSPACE_ROOT = process.cwd();

/**
 * URL 安全校验
 * 防止 SSRF 和访问非预期域名
 */
function validateUrl(url: string): string {
  let parsed: URL;
  try {
    parsed = new URL(url);
  } catch {
    throw new Error(`无效的 URL 格式: ${url}`);
  }

  // 仅允许 HTTPS 协议
  if (parsed.protocol !== 'https:') {
    throw new Error(`仅支持 HTTPS 协议，当前协议: ${parsed.protocol}`);
  }

  // 域名白名单校验
  const hostname = parsed.hostname.toLowerCase();
  const isAllowed = ALLOWED_DOMAINS.some(domain => 
    hostname === domain || hostname.endsWith('.' + domain)
  );
  
  if (!isAllowed) {
    throw new Error(`仅允许访问 Facebook 域名，当前域名: ${hostname}`);
  }

  // 防止访问内网地址
  if (hostname === 'localhost' || 
      hostname.startsWith('127.') || 
      hostname.startsWith('10.') ||
      hostname.startsWith('192.168.') ||
      hostname.match(/^172\.(1[6-9]|2[0-9]|3[0-1])\./)) {
    throw new Error(`禁止访问内网地址: ${hostname}`);
  }

  return url;
}

/**
 * 路径安全校验
 * 防止路径遍历攻击
 */
function validatePath(outputPath: string): string {
  // 规范化路径
  const resolved = path.resolve(outputPath);
  
  // 检查是否在工作目录内
  if (!resolved.startsWith(WORKSPACE_ROOT)) {
    throw new Error(`输出路径必须在工作目录内，当前路径: ${resolved}`);
  }

  // 防止路径遍历
  const normalized = path.normalize(outputPath);
  if (normalized.includes('..')) {
    throw new Error(`路径不允许包含上级目录引用: ${outputPath}`);
  }

  // 检查文件扩展名
  if (!resolved.endsWith('.png') && !resolved.endsWith('.jpg') && !resolved.endsWith('.jpeg')) {
    throw new Error(`仅允许输出图片文件 (.png/.jpg/.jpeg)`);
  }

  return resolved;
}

interface ScreenshotOptions {
  url: string;
  outputPath?: string;
  viewport?: { width: number; height: number };
  fullPage?: boolean;
  scrollCount?: number; // 滚动次数（用于长帖子截取更多内容）
}

async function waitForRender(page: Page, ms: number = ELEMENT_WAIT_MS): Promise<void> {
  await page.waitForLoadState('networkidle').catch(() => {});
  await page.waitForTimeout(ms);
}

async function scrollToElement(page: Page, selector: string): Promise<void> {
  try {
    const element = page.locator(selector).first();
    if (await element.count() > 0) {
      await element.scrollIntoViewIfNeeded();
      await page.waitForTimeout(SCROLL_DELAY_MS);
    }
  } catch {
    // 元素不存在，忽略
  }
}

async function scrollPage(page: Page, count: number = 3): Promise<void> {
  for (let i = 0; i < count; i++) {
    await page.evaluate(() => window.scrollBy(0, window.innerHeight * 0.6));
    await page.waitForTimeout(SCROLL_DELAY_MS);
  }
}

async function attemptElementScreenshot(
  page: Page,
  selectors: string[]
): Promise<Buffer | null> {
  for (const selector of selectors) {
    try {
      const element = page.locator(selector).first();
      if (await element.count() > 0) {
        const buffer = await element.screenshot({ type: 'png' });
        console.log(`✅ 成功截取元素: ${selector}`);
        return buffer;
      }
    } catch (e) {
      // 当前选择器失败，尝试下一个
    }
  }
  return null;
}

async function attemptViewportScreenshot(page: Page): Promise<Buffer | null> {
  try {
    const buffer = await page.screenshot({ type: 'png', fullPage: false });
    console.log('✅ 成功截取当前可视区域');
    return buffer;
  } catch (e) {
    return null;
  }
}

async function attemptFullPageScreenshot(page: Page): Promise<Buffer | null> {
  try {
    // 先滚到底部触发懒加载
    const previousHeight = await page.evaluate(() => document.body.scrollHeight);
    await page.evaluate(() => window.scrollTo(0, document.body.scrollHeight));
    await page.waitForTimeout(1500);

    const newHeight = await page.evaluate(() => document.body.scrollHeight);
    const scrollCount = Math.ceil((newHeight - previousHeight) / (window.innerHeight * 0.8));

    // 滚动触发所有图片/视频懒加载
    for (let i = 0; i < scrollCount; i++) {
      await page.evaluate(() => window.scrollBy(0, window.innerHeight * 0.8));
      await page.waitForTimeout(800);
    }

    await page.evaluate(() => window.scrollTo(0, 0));
    await page.waitForTimeout(1000);

    const buffer = await page.screenshot({ type: 'png', fullPage: true });
    console.log(`✅ 成功截取整页（含 ${scrollCount + 1} 屏）`);
    return buffer;
  } catch (e) {
    return null;
  }
}

async function saveScreenshot(buffer: Buffer, outputPath: string): Promise<string> {
  // 安全校验路径
  const resolved = validatePath(outputPath);
  
  const dir = path.dirname(resolved);
  if (!fs.existsSync(dir)) {
    fs.mkdirSync(dir, { recursive: true });
  }
  fs.writeFileSync(resolved, buffer);
  console.log(`💾 截图已保存: ${resolved}`);
  return resolved;
}

async function fbScreenshot(options: ScreenshotOptions): Promise<{ success: boolean; path?: string; error?: string }> {
  const {
    url,
    outputPath = DEFAULT_OUTPUT,
    viewport = DEFAULT_VIEWPORT,
    fullPage = false,
    scrollCount = 3,
  } = options;

  let browser: Browser | null = null;

  try {
    // 安全校验 URL
    const safeUrl = validateUrl(url);
    
    console.log(`\n🔵 开始截图任务`);
    console.log(`   URL: ${safeUrl}`);
    console.log(`   输出: ${outputPath}`);

    browser = await chromium.launch({ headless: true });
    const context = await browser.newContext({
      viewport,
      userAgent:
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
      locale: 'zh-CN',
    });
    const page = await context.newPage();

    // 设置反爬虫标志
    await page.addInitScript(() => {
      Object.defineProperty(navigator, 'webdriver', { get: () => false });
    });

    console.log('\n🟢 正在加载页面...');
    await page.goto(safeUrl, { waitUntil: 'domcontentloaded', timeout: 30000 });
    await waitForRender(page, 3000);

    let buffer: Buffer | null = null;
    let method = '';

    // ========== FB 专用元素选择器列表 ==========
    const fbPostSelectors = [
      // 通用帖子容器
      '[data-pagelet*="FeedUnit"]',
      '[data-pagelet="TahoeRightRail"]',
      // 群组帖子
      '[role="article"]',
      // 评论区
      '[data-pagelet*="Comment"]',
      // DIV 帖子（降级方案）
      'div[style*="transform"]',
    ];

    // 策略 1: FB 元素截图
    if (!fullPage) {
      buffer = await attemptElementScreenshot(page, fbPostSelectors);
      if (buffer) method = 'FB元素';
    }

    // 策略 2: 整页截图（fullPage=true 或策略1失败）
    if (!buffer) {
      if (fullPage) {
        buffer = await attemptFullPageScreenshot(page);
        method = '整页截图';
      } else {
        // 先尝试滚动截取更多内容
        await scrollPage(page, scrollCount);
        await page.waitForTimeout(1500);

        // 尝试可视区域截图
        buffer = await attemptViewportScreenshot(page);
        if (buffer) method = '可视区域';

        // 仍失败则降级到整页截图
        if (!buffer) {
          await page.evaluate(() => window.scrollTo(0, 0));
          buffer = await attemptFullPageScreenshot(page);
          method = '整页截图(降级)';
        }
      }
    }

    if (!buffer) {
      return { success: false, error: '所有截图策略均失败' };
    }

    const savedPath = await saveScreenshot(buffer, outputPath);
    console.log(`\n✅ 截图完成 [方法: ${method}]`);
    console.log(`   文件: ${savedPath}`);
    console.log(`   大小: ${(buffer.length / 1024).toFixed(1)} KB`);

    return { success: true, path: savedPath };
  } catch (error: any) {
    console.error(`\n❌ 截图失败: ${error.message}`);
    return { success: false, error: error.message };
  } finally {
    if (browser) await browser.close();
  }
}

// ========== CLI 入口 ==========
async function main() {
  const args = process.argv.slice(2);
  const url = args[0];
  const outputPath = args[1] || DEFAULT_OUTPUT;

  if (!url) {
    console.error('用法: npx tsx fb_screenshot.ts <POST_URL> [OUTPUT_PATH]');
    console.error('示例: npx tsx fb_screenshot.ts "https://www.facebook.com/groups/xxx/posts/yyy" "./out.png"');
    process.exit(1);
  }

  const result = await fbScreenshot({ url, outputPath });
  if (!result.success) {
    console.error(`截图失败: ${result.error}`);
    process.exit(1);
  }
}

// 允许直接运行或被导入
if (require.main === module) {
  main().catch((e) => {
    console.error(e);
    process.exit(1);
  });
}

export { fbScreenshot, ScreenshotOptions };
