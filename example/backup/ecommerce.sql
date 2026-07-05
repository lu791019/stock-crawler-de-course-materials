-- 建立資料庫
CREATE DATABASE IF NOT EXISTS test_ecommerce;
USE test_ecommerce;

-- 建立資料表
CREATE TABLE users (
    user_id INT PRIMARY KEY,
    name VARCHAR(50),
    email VARCHAR(100),
    created_at DATE
);

CREATE TABLE products (
    product_id INT PRIMARY KEY,
    name VARCHAR(100),
    category VARCHAR(50),
    price INT
);

CREATE TABLE orders (
    order_id INT PRIMARY KEY,
    user_id INT,
    product_id INT,
    order_date DATE,
    quantity INT,
    total_amount INT,
    FOREIGN KEY (user_id) REFERENCES users(user_id),
    FOREIGN KEY (product_id) REFERENCES products(product_id)
);

-- 插入測試使用者
INSERT INTO users VALUES
(1, 'Alice', 'alice@example.com', '2024-01-05'),
(2, 'Bob', 'bob@example.com', '2024-02-10'),
(3, 'Charlie', 'charlie@example.com', '2024-03-15');

-- 插入測試商品
INSERT INTO products VALUES
(101, 'iPhone 15', 'Electronics', 32900),
(102, 'AirPods Pro', 'Electronics', 7500),
(103, 'MacBook Air', 'Electronics', 42000),
(104, 'Coffee Maker', 'Home Appliances', 2500),
(105, 'Office Chair', 'Furniture', 5600);

-- 插入測試訂單
INSERT INTO orders VALUES
(1001, 1, 101, '2024-04-01', 1, 32900),
(1002, 1, 102, '2024-04-01', 1, 7500),
(1003, 2, 102, '2024-04-03', 1, 7500),
(1004, 1, 105, '2024-04-05', 1, 5600),
(1005, 3, 103, '2024-04-06', 1, 42000),
(1006, 3, 104, '2024-04-06', 2, 5000);
