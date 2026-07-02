-- 建立學生表
CREATE TABLE students (
    student_id INT PRIMARY KEY,
    student_no VARCHAR(10),
    name VARCHAR(50),
    gender VARCHAR(10),
    age INT,
    department VARCHAR(50)
);

-- 插入至少 30 筆資料
INSERT INTO students VALUES
(1, 'S001', 'Alice', 'Female', 20, 'Computer Science'),
(2, 'S002', 'Bob', 'Male', 22, 'Mathematics'),
(3, 'S003', 'Charlie', 'Male', 21, 'Physics'),
(4, 'S004', 'David', 'Male', 23, 'Computer Science'),
(5, 'S005', 'Eve', 'Female', 19, 'Business'),
(6, 'S006', 'Frank', 'Male', 24, 'Mathematics'),
(7, 'S007', 'Grace', 'Female', 22, 'Computer Science'),
(8, 'S008', 'Hank', 'Male', 20, 'Physics'),
(9, 'S009', 'Ivy', 'Female', 21, 'Business'),
(10, 'S010', 'Jack', 'Male', 20, 'Computer Science'),
(11, 'S011', 'Kelly', 'Female', 23, 'Mathematics'),
(12, 'S012', 'Leo', 'Male', 19, 'Business'),
(13, 'S013', 'Mia', 'Female', 22, 'Computer Science'),
(14, 'S014', 'Nick', 'Male', 21, 'Physics'),
(15, 'S015', 'Olivia', 'Female', 24, 'Business'),
(16, 'S016', 'Paul', 'Male', 20, 'Mathematics'),
(17, 'S017', 'Queen', 'Female', 23, 'Computer Science'),
(18, 'S018', 'Ray', 'Male', 21, 'Physics'),
(19, 'S019', 'Sophia', 'Female', 22, 'Business'),
(20, 'S020', 'Tom', 'Male', 19, 'Mathematics'),
(21, 'S021', 'Uma', 'Female', 20, 'Computer Science'),
(22, 'S022', 'Victor', 'Male', 23, 'Business'),
(23, 'S023', 'Wendy', 'Female', 24, 'Physics'),
(24, 'S024', 'Xavier', 'Male', 22, 'Mathematics'),
(25, 'S025', 'Yvonne', 'Female', 21, 'Business'),
(26, 'S026', 'Zack', 'Male', 20, 'Computer Science'),
(27, 'S027', 'Ella', 'Female', 22, 'Mathematics'),
(28, 'S028', 'Felix', 'Male', 23, 'Physics'),
(29, 'S029', 'Gina', 'Female', 21, 'Business'),
(30, 'S030', 'Henry', 'Male', 24, 'Computer Science');
