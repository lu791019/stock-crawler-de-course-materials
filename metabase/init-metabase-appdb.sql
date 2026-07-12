-- Metabase 設定庫（application database）初始化
-- 掛載到 MySQL 的 /docker-entrypoint-initdb.d/：只在 volume 第一次建立時自動執行
-- 既有 volume 不會重跑，手動建立指令見課程手冊08 Step 2（IF NOT EXISTS，重複執行無副作用）
CREATE DATABASE IF NOT EXISTS metabasedb;
CREATE USER IF NOT EXISTS 'metabase_app'@'%' IDENTIFIED BY '1234';
GRANT ALL PRIVILEGES ON metabasedb.* TO 'metabase_app'@'%';
