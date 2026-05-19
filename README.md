# 居家牙醫申請優化系統

Hanna 跟同事用的內部工具：填表 → 生成公會制式 PDF → 手動寄出 → 追蹤狀態。

## 本機跑

```bash
cd dental-app
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

cp .streamlit/secrets.toml.example .streamlit/secrets.toml
# 填入 app_password 跟 Supabase 連線資訊

streamlit run app.py
```

## Supabase 一次性設定

1. 到 https://supabase.com 建一個新 project
2. SQL Editor 跑：

   ```sql
   create table applications (
     id uuid primary key default gen_random_uuid(),
     created_by text not null,
     created_at timestamptz default now(),
     updated_at timestamptz default now(),
     status text default 'draft',
     case_name text,
     payload jsonb not null,
     uploads jsonb default '[]'::jsonb
   );

   create or replace function applications_set_updated_at()
   returns trigger as $$
   begin
     new.updated_at := now();
     return new;
   end;
   $$ language plpgsql;

   create trigger applications_set_updated_at_trigger
     before update on applications
     for each row
     execute function applications_set_updated_at();
   ```

3. Storage → Create bucket → 命名 `dental-uploads`，設為 **Private**
4. Project Settings → API 拿 URL 跟 `service_role` key，填到 `secrets.toml`

## 部署到 Streamlit Cloud

1. 把 `dental-app/` 推上 GitHub
2. https://share.streamlit.io 連 repo，main file 設 `app.py`
3. Settings → Secrets 把 `secrets.toml` 內容貼上

## 字型授權

`assets/fonts/kaiti.ttf` 是教育部標準楷書字形檔 5.1 版（edukai-5.1_20251208.ttf）。

採 [創用 CC「姓名標示-禁止改作」3.0 台灣](https://language.moe.gov.tw/001/Upload/Files/site_content/M0001/edukai.pdf) 授權。引用時請標示「中華民國教育部」。鏡像來源：[Jiehong/TW-fonts](https://github.com/Jiehong/TW-fonts)。

## 還沒做的

- [ ] **PDF 套版**：等 Hanna 把公會範本放到 `assets/templates/official_form.pdf`
- [ ] 補件提醒（Phase 3）
- [ ] 月報匯出（Phase 3）
