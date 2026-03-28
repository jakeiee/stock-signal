/**
 * Trendonify 估值数据爬虫
 * 
 * 使用 Playwright 获取 https://trendonify.com/pe-ratio 的数据
 * 
 * 运行: node trendonify_scraper.js
 */

const { chromium } = require('playwright');
const fs = require('fs');
const path = require('path');

async function scrapeTrendonify() {
    console.log('启动浏览器...');
    const browser = await chromium.launch({ 
        headless: true,
        args: ['--no-sandbox', '--disable-setuid-sandbox']
    });
    
    const context = await browser.newContext({
        userAgent: 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36'
    });
    
    const page = await context.newPage();
    
    const url = 'https://trendonify.com/pe-ratio';
    console.log(`访问 ${url}...`);
    
    try {
        await page.goto(url, { timeout: 30000 });
        
        // 等待数据加载
        console.log('等待数据加载...');
        await page.waitForTimeout(30000);
        
        console.log('页面加载完成，提取数据...');
        
        // 从表格提取数据
        const tableData = await page.evaluate(() => {
            const result = [];
            const tables = document.querySelectorAll('table');
            
            tables.forEach(table => {
                const headers = [];
                const headerCells = table.querySelectorAll('th');
                headerCells.forEach(th => {
                    headers.push(th.textContent.trim().toLowerCase());
                });
                
                const rows = table.querySelectorAll('tr');
                rows.forEach(row => {
                    const cells = row.querySelectorAll('td');
                    if (cells.length >= 2) {
                        const rowData = {};
                        cells.forEach((cell, idx) => {
                            if (headers[idx]) {
                                rowData[headers[idx]] = cell.textContent.trim();
                            }
                        });
                        if (Object.keys(rowData).length > 0) {
                            result.push(rowData);
                        }
                    }
                });
            });
            
            return result;
        });
        
        console.log(`从表格提取到 ${tableData.length} 条数据`);
        
        // 打印前几条数据看看结构
        if (tableData.length > 0) {
            console.log('前3条数据:', JSON.stringify(tableData.slice(0, 3), null, 2));
        }
        
        // 解析数据，提取目标市场
        // 目标市场关键词映射
        const marketKeywords = {
            'US': ['united states', 's&p', 'spx', 'sp 500', 'usa'],
            'HK': ['hang seng', 'hsi', 'hong kong'],
            'JP': ['japan'],
            'KR': ['korea', 'kospi']
        };
        
        // 估值标签映射
        const getLabel = (valStr) => {
            const val = (valStr || '').toLowerCase();
            if (val.includes('expensive') || val.includes('overvalued')) {
                const pctMatch = valStr.match(/(\d+\.?\d*)%/);
                if (pctMatch) {
                    const pct = parseFloat(pctMatch[1]);
                    if (pct >= 81) return '昂贵';
                    if (pct >= 61) return '高估';
                    if (pct >= 41) return '合理';
                    if (pct >= 21) return '低估';
                    return '有吸引力';
                }
            }
            if (val.includes('overvalued')) return '高估';
            if (val.includes('expensive')) return '昂贵';
            if (val.includes('fair')) return '合理';
            if (val.includes('undervalued')) return '低估';
            return '';
        };
        
        // 解析百分位的辅助函数
        const parsePct = (val) => {
            if (!val) return null;
            const str = String(val).replace('%', '').trim();
            const num = parseFloat(str);
            return isNaN(num) ? null : num;
        };
        
        const result = {
            source: 'trendonify',
            date: new Date().toISOString().split('T')[0],
            note: '通过Playwright动态获取'
        };
        
        // 查找目标市场
        tableData.forEach(row => {
            // country列包含国家名
            const country = (row.country || '').toLowerCase();
            // ticker列包含代码如SPX, HSI等
            const ticker = (row.ticker || '').toUpperCase();
            
            for (const [market, keywords] of Object.entries(marketKeywords)) {
                const match = keywords.some(k => country.includes(k)) || 
                              keywords.some(k => ticker.includes(k.toUpperCase()));
                
                if (match) {
                    // 获取PE值 - 尝试多种列名
                    const peStr = row['p/e ratio ↓'] || row['pe'] || row['p/e ratio'] || '';
                    const pe = parseFloat(peStr);
                    
                    // 获取TICKER
                    const ticker = row['ticker'] || '';
                    
                    // 获取10年百分位
                    const pctStr = row['percentile rank (10y)'] || row['10y %'] || row['percentile'] || '';
                    const pct = parsePct(pctStr);
                    
                    // 获取20年百分位
                    const pct20Str = row['percentile rank (20y)'] || row['20y %'] || '';
                    const pct_20y = parsePct(pct20Str);
                    
                    // 获取10年估值标签
                    const valStr = row['valuation (10y)'] || row['valuation'] || '';
                    const label = getLabel(valStr) || (pct ? getLabel(pct + '%') : '');
                    
                    // 获取20年估值标签
                    const val20Str = row['valuation (20y)'] || '';
                    const label_20y = getLabel(val20Str) || (pct_20y ? getLabel(pct_20y + '%') : '');
                    
                    // 获取最后更新日期
                    const lastUpdate = row['last update'] || '';
                    
                    if (!isNaN(pe) && pct !== null) {
                        result[market] = {
                            pe: pe,
                            ticker: ticker,
                            pct_10y: pct,
                            pct_20y: pct_20y,
                            label_10y: label || getLabel(pct + '%'),
                            label_20y: label_20y || (pct_20y ? getLabel(pct_20y + '%') : ''),
                            last_update: lastUpdate
                        };
                        console.log(`找到 ${market}: TICKER=${ticker}, PE=${pe}, 10Y=${pct}%, 20Y=${pct_20y}%`);
                    }
                    break;
                }
            }
        });
        
        console.log('最终结果:');
        console.log(JSON.stringify(result, null, 2));
        
        // 保存到文件
        const dataDir = path.join(__dirname, '..', 'data');
        if (!fs.existsSync(dataDir)) {
            fs.mkdirSync(dataDir, { recursive: true });
        }
        const cachePath = path.join(dataDir, 'trendonify_cache.json');
        fs.writeFileSync(cachePath, JSON.stringify(result, null, 2));
        console.log(`数据已保存到 ${cachePath}`);
        
        await browser.close();
        return result;
        
    } catch (error) {
        console.error('抓取失败:', error.message);
        await browser.close();
        throw error;
    }
}

scrapeTrendonify().catch(console.error);
