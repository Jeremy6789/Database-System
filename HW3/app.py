import json
import re
import os
from flask import Flask, render_template, request, redirect, url_for, flash
from pymongo import MongoClient
from bson import json_util # 匯入 bson 工具，用來處理 MongoDB 的 ObjectId 轉換
from bson.objectid import ObjectId
from dotenv import load_dotenv

load_dotenv()

# --- Flask App 初始化 ---
app = Flask(__name__)
# 設定一個 secret_key 來使用 flash 訊息功能，這是一串隨機的密鑰
app.secret_key = os.getenv("SECRET_KEY", "a_default_secret_key_if_not_set")

# --- MongoDB 連線設定 ---
# 連接到你本地的 MongoDB 實例 (localhost:27017)
MONGO_URI = os.getenv("MONGO_URI") # <--- **最重要的修改**
if not MONGO_URI:
    raise Exception("MONGO_URI environment variable not set!")

client = MongoClient(MONGO_URI)


# 選擇你的資料庫和集合
# 如果它們不存在，MongoDB 會在第一次新增資料時自動建立它們
db = client.company_db
employees_collection = db.employees

# --- 路由 (Routes) 設定 ---

@app.route('/')
def index():
    """首頁，現在同時處理顯示所有員工和搜尋結果"""
    # 從 URL 參數中獲取名為 'query' 的值 (例如 /?query=John)
    query = request.args.get('query')
    
    # 建立一個查詢過濾器
    search_filter = {}
    
    if query:
        # 如果使用者輸入了查詢條件
        # 使用正規表示式來進行不分大小寫的模糊匹配
        # re.escape() 是為了防止使用者輸入特殊字元造成錯誤
        regex = re.compile(re.escape(query), re.IGNORECASE)
        
        # 建立一個跨多個欄位的 OR 查詢
        search_filter = {
            "$or": [
                {"employee_id": {"$regex": regex}},
                {"name": {"$regex": regex}},
                {"department": {"$regex": regex}},
                {"position": {"$regex": regex}},
                {"status": {"$regex": regex}}
            ]
        }
    
    # 根據 search_filter 執行 find()，如果 filter 是空的 {}，則會找到所有文件
    all_employees = list(employees_collection.find(search_filter))
    
    # 將 BSON 轉換為 JSON 安全的格式
    employees_json_safe = json.loads(json_util.dumps(all_employees))
    
    # 將查詢結果和使用者輸入的 query 關鍵字一起傳遞給模板
    return render_template('index.html', employees=employees_json_safe, query=query)

@app.route('/add_many', methods=['POST'])
def add_many():
    """處理來自前端的批次新增員工請求"""
    try:
        # 從表單的 textarea (name="employees_json") 中獲取使用者輸入的 JSON 字串
        employees_json_str = request.form['employees_json']
        # 將 JSON 字串解析成 Python 的 list of dictionaries
        employees_data = json.loads(employees_json_str)
        
        # 進行一個簡單的驗證，確保資料是 list 格式 (對應 JSON 的 array)
        if not isinstance(employees_data, list):
            flash("Add failed: Input must be a JSON array!", "error")
            return redirect(url_for('index'))
            
        # 執行 insert_many 操作，將資料陣列寫入資料庫
        result = employees_collection.insert_many(employees_data)
        # 使用 flash 訊息回饋給使用者操作結果
        flash(f"Successfully added {len(result.inserted_ids)} new employees!", "success")

    except json.JSONDecodeError:
        # 如果 JSON 格式錯誤，捕捉例外並回報錯誤
        flash("Add failed: Invalid JSON format!", "error")
    except Exception as e:
        # 捕捉其他可能的錯誤
        flash(f"An unknown error occurred: {e}", "error")
        
    # 操作完成後，重新導向回首頁
    return redirect(url_for('index'))

@app.route('/update_many', methods=['POST'])
def update_many():
    """處理批次更新員工的請求"""
    try:
        # 獲取更新條件 (filter) 和更新內容 (data) 的 JSON 字串
        filter_json_str = request.form['update_filter']
        update_json_str = request.form['update_data']
        
        # 將 JSON 字串轉成 Python 的 dictionary
        filter_query = json.loads(filter_json_str)
        update_data = json.loads(update_json_str)
        
        # 執行 update_many 操作，注意要使用 MongoDB 的 "$set" 運算子
        result = employees_collection.update_many(filter_query, {"$set": update_data})
        flash(f"Successfully updated {result.modified_count} employee records!", "success")

    except json.JSONDecodeError:
        flash("Update failed: Filter or Update Data is not valid JSON!", "error")
    except Exception as e:
        flash(f"An unknown error occurred: {e}", "error")

    return redirect(url_for('index'))

@app.route('/delete_many', methods=['POST'])
def delete_many():
    """處理批次刪除員工的請求"""
    try:
        # 獲取刪除條件的 JSON 字串
        filter_json_str = request.form['delete_filter']
        filter_query = json.loads(filter_json_str)
        
        # 執行 delete_many 操作
        result = employees_collection.delete_many(filter_query)
        flash(f"Successfully deleted {result.deleted_count} employee records!", "success")
        
    except json.JSONDecodeError:
        flash("Delete failed: Filter is not valid JSON!", "error")
    except Exception as e:
        flash(f"An unknown error occurred: {e}", "error")

    return redirect(url_for('index'))

@app.route('/edit/<id>')
def edit_employee(id):
    """
    顯示單一員工的編輯頁面。
    這是一個 GET 請求。
    """
    try:
        # 將從 URL 傳來的字串 ID 轉換成 MongoDB 的 ObjectId 物件
        employee_id_obj = ObjectId(id)
        
        # 使用 find_one 根據 ObjectId 查找該員工的資料
        employee = employees_collection.find_one({"_id": employee_id_obj})
        
        if employee:
            # 如果找到了員工，就渲染 edit.html 樣板，並將員工資料傳遞過去
            return render_template('edit.html', employee=employee)
        else:
            # 如果找不到對應的員工
            flash("Employee not found!", "error")
            return redirect(url_for('index'))
            
    except Exception as e:
        # 如果 ID 格式錯誤或其他問題
        flash(f"An error occurred: {e}", "error")
        return redirect(url_for('index'))

@app.route('/update/<id>', methods=['POST'])
def update_employee(id):
    """
    處理從編輯頁面提交的更新表單。
    這是一個 POST 請求。
    """
    try:
        employee_id_obj = ObjectId(id)
        
        # 從提交的表單中獲取更新後的資料
        updated_data = {
            "employee_id": request.form['employee_id'],
            "name": request.form['name'],
            "department": request.form['department'],
            "position": request.form['position'],
            "age": int(request.form['age']), # 將 age 轉為整數
            "status": request.form['status']
        }
        
        # 在資料庫中更新該員工的資料
        employees_collection.update_one(
            {"_id": employee_id_obj},
            {"$set": updated_data}
        )
        
        flash("Employee updated successfully!", "success")
        
    except ValueError:
        flash("Update failed: Age must be a number.", "error")
    except Exception as e:
        flash(f"An update error occurred: {e}", "error")
        
    # 無論成功或失敗，都重導向回首頁
    return redirect(url_for('index'))

# --- 啟動 App ---
# 確保這個腳本是直接被執行，而不是被匯入的
if __name__ == '__main__':
    # debug=True 模式會在開發時提供詳細錯誤訊息，並且在程式碼變更時自動重啟伺服器
    app.run(debug=True)