import os
import json
import gspread
from google.oauth2.service_account import Credentials

class SheetManager:
    def __init__(self):
        # 1. 获取凭证
        raw_key = os.getenv("GCP_SA_KEY")
        if not raw_key:
            raise ValueError("❌ 环境变量 GCP_SA_KEY 未找到")
        
        try:
            creds_dict = json.loads(raw_key)
            creds = Credentials.from_service_account_info(
                creds_dict,
                scopes=["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
            )
        except json.JSONDecodeError:
            raise ValueError("❌ GCP_SA_KEY JSON 解析失败，请检查格式")

        # 2. 连接客户端
        print("   >>> [System] 初始化 Google Sheets (智能连接版)...")
        try:
            self.client = gspread.authorize(creds)
            print("   ✅ Google Auth 认证成功")
        except Exception as e:
            raise Exception(f"❌ Google Auth 失败: {e}")

        # 3. 连接表格
        sheet_name_or_id = os.getenv("SHEET_NAME")
        if not sheet_name_or_id:
            raise ValueError("❌ 环境变量 SHEET_NAME 未找到")

        try:
            if len(sheet_name_or_id) > 20: 
                self.sh = self.client.open_by_key(sheet_name_or_id)
                print(f"   ✅ [成功] 已通过 ID 连接到表格！")
            else:
                print(f"   >>> 正在尝试按【文件名】打开: '{sheet_name_or_id}'...")
                self.sh = self.client.open(sheet_name_or_id)
                print(f"   ✅ [成功] 已通过文件名连接到表格！")
        except gspread.SpreadsheetNotFound:
            print(f"   ❌ 找不到名为 '{sheet_name_or_id}' 的表格。")
            raise

        self.sheet = self.sh.sheet1

    def get_all_stocks(self):
        """
        获取所有股票配置
        New Format: Code, Date, Price, Qty, Timeframe(Col5), Bars(Col6)
        """
        all_values = self.sheet.get_all_values()
        if not all_values: return {}
        
        data_rows = all_values[1:]
        stocks = {}
        for row in data_rows:
            if not row or not row[0].strip(): continue
            
            raw_symbol = row[0].strip()
            digits = ''.join(filter(str.isdigit, raw_symbol))
            symbol = digits.zfill(6)
            
            # 安全获取各项配置
            buy_date = row[1].strip() if len(row) > 1 else ""
            price = row[2].strip() if len(row) > 2 else ""
            qty = row[3].strip() if len(row) > 3 else ""
            
            # === 新增自定义列 ===
            # 如果表格里没填，默认给 None，交给 main.py 处理默认值
            timeframe = row[4].strip() if len(row) > 4 else "5"
            bars = row[5].strip() if len(row) > 5 else "500"
            note = row[6].strip() if len(row) > 6 else ""
            
            # 简单的清洗，确保不为空
            if not timeframe: timeframe = "5"
            if not bars: bars = "500"
            
            stocks[symbol] = {
                "date": buy_date, 
                "price": price, 
                "qty": qty,
                "timeframe": timeframe,
                "bars": bars,
                "note": note
            }
        return stocks

    def add_or_update_stock(self, symbol, date='', price='', qty=''):
        """添加或更新 (保持原样，新增列需手动在表格调整或后续升级指令)"""
        clean_symbol = ''.join(filter(str.isdigit, str(symbol))).zfill(6)
        print(f"   🔍 正在查找股票: {clean_symbol}")
        
        try:
            cell = self.sheet.find(clean_symbol)
            action_type = ""
            
            if cell:
                print(f"   Found at Row {cell.row}. Updating...")
                row = cell.row
                if date: self.sheet.update_cell(row, 2, str(date))
                if price: self.sheet.update_cell(row, 3, str(price))
                if qty: self.sheet.update_cell(row, 4, str(qty))
                action_type = "✅ 已更新"
            else:
                print(f"   Not found. Appending new row...")
                # 默认追加时，周期和根数留空(使用默认)
                self.sheet.append_row([clean_symbol, str(date), str(price), str(qty), "5", "500"])
                action_type = "🆕 新增关注"

            show_date = date if date else "-"
            show_price = price if price else "-"
            show_qty = qty if qty else "-"

            return (
                f"{action_type} {clean_symbol}\n"
                f"本次变动: {show_date} | {show_price} | {show_qty}"
            )
                
        except Exception as e:
            print(f"   ❌ 操作表格失败: {e}")
            raise e

    def remove_stock(self, symbol):
        clean_symbol = ''.join(filter(str.isdigit, str(symbol))).zfill(6)
        try:
            cell = self.sheet.find(clean_symbol)
            if cell:
                self.sheet.delete_rows(cell.row)
                return f"🗑️ 已移除 {clean_symbol}"
            else:
                return f"⚠️ 未找到 {clean_symbol}"
        except Exception as e:
            return f"❌ 删除失败: {e}"

    def get_portfolio_summary(self):
        stocks = self.get_all_stocks()
        if not stocks:
            return "\n📭 当前关注列表为空"

        summary_lines = [f"\n📊 当前持仓汇总 ({len(stocks)}):"]
        summary_lines.append("────────────────")
        
        for symbol, info in stocks.items():
            details = []
            if info['price']: details.append(f"💰{info['price']}")
            # 显示周期设置
            tf = info.get('timeframe', '5')
            bar = info.get('bars', '500')
            details.append(f"⏱️{tf}m/{bar}")
            
            detail_str = f" ({' '.join(details)})" if details else ""
            summary_lines.append(f"🔹 `{symbol}`{detail_str}")
        
        return "\n".join(summary_lines)
