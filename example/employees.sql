-- 建立員工表
CREATE TABLE employees (
    emp_id INT PRIMARY KEY,
    name VARCHAR(50),
    department VARCHAR(50),
    job_title VARCHAR(50),
    salary INT,
    hire_date DATE
);

-- 插入測試資料
INSERT INTO employees VALUES
(1, 'Alice', 'HR', 'HR Manager', 60000, '2020-03-15'),
(2, 'Bob', 'IT', 'Software Engineer', 75000, '2021-07-10'),
(3, 'Charlie', 'Finance', 'Accountant', 50000, '2019-11-20'),
(4, 'David', 'IT', 'Data Engineer', 80000, '2022-01-05'),
(5, 'Eve', 'Marketing', 'Marketing Specialist', 55000, '2021-05-01'),
(6, 'Frank', 'Finance', 'Financial Analyst', 52000, '2023-02-10'),
(7, 'Grace', 'IT', 'DevOps Engineer', 77000, '2020-12-25'),
(8, 'Hank', 'Marketing', 'Content Creator', 48000, '2022-08-18'),
(9, 'Ivy', 'HR', 'Recruiter', 45000, '2023-04-02'),
(10, 'Jack', 'IT', 'Software Engineer', 73000, '2021-09-14');
