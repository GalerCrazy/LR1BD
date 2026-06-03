import sqlite3
import csv


class SQLTableManager:
    def __init__(self, db_name):
        self.conn = sqlite3.connect(db_name)
        self.cursor = self.conn.cursor()

    def get_column_sorted(self, table, column, asc=True):
        order = "ASC" if asc else "DESC"
        self.cursor.execute(f"SELECT {column} FROM {table} ORDER BY {column} {order}")
        result = self.cursor.fetchall()

        values = []
        for row in result:
            values.append(row[0])
        return values

    def get_rows_by_id_range(self, table, start, end):
        self.cursor.execute(f"SELECT * FROM {table} WHERE id BETWEEN {start} AND {end}")
        return self.cursor.fetchall()

    def delete_rows_by_id_range(self, table, start, end):
        self.cursor.execute(f"DELETE FROM {table} WHERE id BETWEEN {start} AND {end}")
        self.conn.commit()

    def get_table_structure(self, table):
        self.cursor.execute(f"PRAGMA table_info({table})")
        return self.cursor.fetchall()

    def find_rows_by_value(self, table, column, value):
        self.cursor.execute(f"SELECT * FROM {table} WHERE {column} = ?", (value,))
        return self.cursor.fetchall()

    def drop_table(self, table):
        self.cursor.execute(f"DROP TABLE IF EXISTS {table}")
        self.conn.commit()

    def add_column(self, table, column, type_):
        self.cursor.execute(f"PRAGMA table_info({table})")
        columns_info = self.cursor.fetchall()

        columns = []
        for col in columns_info:
            columns.append(col[1])

        if column in columns:
            print(f"Столбец {column} уже существует")
            return

        self.cursor.execute(f"ALTER TABLE {table} ADD COLUMN {column} {type_}")
        self.conn.commit()
        print(f"Столбец {column} добавлен")

    def drop_column(self, table, column):
        try:
            self.cursor.execute(f"ALTER TABLE {table} DROP COLUMN {column}")
            self.conn.commit()
            print(f"Столбец {column} удалён")
        except sqlite3.OperationalError:
            print("Удаление столбца не поддерживается в этой версии SQLite")

    def export_to_csv(self, table, filename):
        self.cursor.execute(f"SELECT * FROM {table}")
        data = self.cursor.fetchall()

        column_names = []
        for desc in self.cursor.description:
            column_names.append(desc[0])

        with open(filename, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(column_names)
            writer.writerows(data)

        print(f"Таблица {table} экспортирована в {filename}")

    def import_from_csv(self, table, filename):
        with open(filename, "r", encoding="utf-8") as f:
            reader = csv.reader(f)
            headers = next(reader)

            for row in reader:
                placeholders = ",".join(["?"] * len(row))
                self.cursor.execute(
                    f"INSERT INTO {table} ({','.join(headers)}) VALUES ({placeholders})",
                    row
                )

        self.conn.commit()
        print(f"Данные из {filename} импортированы в {table}")

    def close(self):
        self.conn.close()


db = SQLTableManager("test.db")

db.cursor.execute("""
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT,
    age INTEGER
)
""")
db.conn.commit()

db.cursor.execute("DELETE FROM users")
db.conn.commit()

db.cursor.execute("INSERT INTO users (name, age) VALUES ('Alex', 20)")
db.cursor.execute("INSERT INTO users (name, age) VALUES ('Masha', 18)")
db.cursor.execute("INSERT INTO users (name, age) VALUES ('Ivan', 25)")
db.conn.commit()

db.add_column("users", "email", "TEXT")

print("Все данные:")
print(db.get_rows_by_id_range("users", 1, 10))

print("\nСортировка по возрасту по возрастанию:")
print(db.get_column_sorted("users", "age", True))

print("\nСортировка по возрасту по убыванию:")
print(db.get_column_sorted("users", "age", False))

print("\nПоиск name = Alex:")
print(db.find_rows_by_value("users", "name", "Alex"))

print("\nСтруктура таблицы:")
print(db.get_table_structure("users"))

print("\nЭкспорт в csv:")
db.export_to_csv("users", "users.csv")

db.close()