# Step 3：三個階段各自獨立成檔案

- 上一步（Step 2）：同一支檔案裡已有 fetch / transform / save 三階段與 crawl() 任務函式。
- 這一步：三個階段搬進 client.py / transformer.py / repository.py，設定值抽到 config.py 改讀環境變數；crawl() 留在 main.py。
- 沒動的：三個階段函式的內容、crawl() 的內容。

執行（專案根目錄）：

```bash
uv run python example/evolution/step3_modules/main.py
STORAGE=mysql uv run python example/evolution/step3_modules/main.py      # 換儲存目標
STORAGE=csv,mysql uv run python example/evolution/step3_modules/main.py  # 雙寫
```

驗收：換 STORAGE 的值時，client.py 與 transformer.py 一行都不用改。

完整說明見 課程手冊/補充J 的 Step 3。
