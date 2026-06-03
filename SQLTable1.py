import mysql.connector
import pandas as pd
import os
import datetime
import json
import matplotlib.pyplot as plt

pd.set_option('display.max_rows', None)
pd.set_option('display.width', None)


class SQLTable:
    def __init__(self, db_config, table_name):
        self.db_config = db_config
        self.table_name = table_name
        self.connection = mysql.connector.connect(**db_config)
        self.cursor = self.connection.cursor()
        self.columns = []

        if not self._check_table_exists():
            print(f"Error: Table '{self.table_name}' does not exist. Please use create_table method to create it.")
        else:
            self._update_column_names()

    def _check_table_exists(self):
        query = f"SHOW TABLES LIKE '{self.table_name}'"
        self.cursor.execute(query)
        return self.cursor.fetchone() is not None

    def _update_column_names(self):
        query = f"SHOW COLUMNS FROM {self.table_name}"
        self.cursor.execute(query)
        self.columns = [row[0] for row in self.cursor.fetchall()]

    def create_table(self, columns):
        column_definition = ', '.join(f"`{name}` {type}" for name, type in columns.items())
        query = f"""
        CREATE TABLE IF NOT EXISTS {self.table_name} (
            `id` INT AUTO_INCREMENT PRIMARY KEY,
            {column_definition}
        )
        """
        cursor = self.connection.cursor()
        try:
            cursor.execute(query)
            self.connection.commit()
        finally:
            cursor.close()
        self._update_column_names()
        print(f"Table '{self.table_name}' created with columns {self.columns}.")

    def fetch_all(self):
        cursor = self.connection.cursor()
        try:
            cursor.execute(f"SELECT * FROM {self.table_name}")
            rows = cursor.fetchall()
            column_names = [col[0] for col in cursor.description]
        finally:
            cursor.close()
        return pd.DataFrame(rows, columns=column_names)

    def fetch_all_ordered(self, order_column, ascending=True):
        order_direction = "ASC" if ascending else "DESC"
        cursor = self.connection.cursor()
        try:
            cursor.execute(f"SELECT * FROM {self.table_name} ORDER BY `{order_column}` {order_direction}")
            rows = cursor.fetchall()
            column_names = [col[0] for col in cursor.description]
        finally:
            cursor.close()
        return pd.DataFrame(rows, columns=column_names)

    def fetch_column(self, column_name):
        primary_key = self._find_primary_key()
        if not primary_key:
            print("No primary key found for the table.")
            return pd.DataFrame()

        query = f"SELECT `{primary_key}`, `{column_name}` FROM {self.table_name}"
        cursor = self.connection.cursor()
        try:
            cursor.execute(query)
            rows = cursor.fetchall()
            df = pd.DataFrame(rows, columns=[primary_key, column_name])
        finally:
            cursor.close()

        return df

    def _find_primary_key(self):
        cursor = self.connection.cursor()
        try:
            cursor.execute(f"SHOW KEYS FROM {self.table_name} WHERE Key_name = 'PRIMARY'")
            result = cursor.fetchone()
            if result:
                return result[4]
        finally:
            cursor.close()
        return None

    def insert_row(self, data):
        columns = ', '.join(f"`{k}`" for k in data.keys())
        placeholders = ', '.join(['%s'] * len(data))
        values = tuple(data.values())

        query = f"INSERT INTO {self.table_name} ({columns}) VALUES ({placeholders})"
        cursor = self.connection.cursor()
        try:
            cursor.execute(query, values)
            self.connection.commit()
        finally:
            cursor.close()

    def delete_row_by_id(self, id):
        primary_key = self._find_primary_key()
        if not primary_key:
            print("No primary key found for the table.")
            return False

        query = f"DELETE FROM {self.table_name} WHERE `{primary_key}` = %s"
        cursor = self.connection.cursor()
        try:
            cursor.execute(query, (id,))
            self.connection.commit()
            return True
        finally:
            cursor.close()

    def delete_rows_by_ids(self, ids):
        for id in ids:
            self.delete_row_by_id(id)

    def select_rows_by_ids(self, ids):
        primary_key = self._find_primary_key()
        if not primary_key:
            print("Primary key not found.")
            return pd.DataFrame()

        ids_tuple = tuple(ids)
        query = f"SELECT * FROM {self.table_name} WHERE `{primary_key}` IN {ids_tuple}"
        cursor = self.connection.cursor()
        try:
            cursor.execute(query)
            rows = cursor.fetchall()
            column_names = [i[0] for i in cursor.description]
        finally:
            cursor.close()
        return pd.DataFrame(rows, columns=column_names)

    def select_row_by_id(self, id):
        primary_key = self._find_primary_key()
        if not primary_key:
            print("Primary key not found.")
            return pd.DataFrame()

        query = f"SELECT * FROM {self.table_name} WHERE `{primary_key}` = %s"
        cursor = self.connection.cursor()
        try:
            cursor.execute(query, (id,))
            row = cursor.fetchall()
            column_names = [i[0] for i in cursor.description]
        finally:
            cursor.close()
        return pd.DataFrame(row, columns=column_names)

    def update_column_by_id(self, id, column_name, new_value):
        primary_key = self._find_primary_key()
        if not primary_key:
            print("Primary key not found.")
            return False

        query = f"UPDATE {self.table_name} SET `{column_name}` = %s WHERE `{primary_key}` = %s"
        cursor = self.connection.cursor()
        try:
            cursor.execute(query, (new_value, id))
            self.connection.commit()
            return True
        except Exception as e:
            print(f"Failed to update row: {e}")
            return False
        finally:
            cursor.close()

    def rename_table(self, new_table_name):
        query = f"ALTER TABLE {self.table_name} RENAME TO {new_table_name}"
        self.cursor.execute(query)
        self.connection.commit()
        self.table_name = new_table_name

    def export_to_csv(self):
        df = self.fetch_all()
        downloads_path = os.path.join(os.path.expanduser('~'), 'Downloads')
        if not os.path.exists(downloads_path):
            os.makedirs(downloads_path)
        timestamp = datetime.datetime.now().strftime('%Y-%m-%d_%H-%M-%S')
        file_name = f"{self.table_name}_{timestamp}.csv"
        file_path = os.path.join(downloads_path, file_name)
        df.to_csv(file_path, index=False)
        print(f"Data exported successfully to {file_path}")

    def select_rows_by_id_range(self, start_id, end_id):
        primary_key = self._find_primary_key()
        if not primary_key:
            print("Primary key not found.")
            return pd.DataFrame()

        query = f"SELECT * FROM {self.table_name} WHERE `{primary_key}` BETWEEN %s AND %s"
        cursor = self.connection.cursor()
        try:
            cursor.execute(query, (start_id, end_id))
            rows = cursor.fetchall()
            column_names = [i[0] for i in cursor.description]
        finally:
            cursor.close()
        return pd.DataFrame(rows, columns=column_names)

    def select_rows_by_column_value(self, column_name, value):
        query = f"SELECT * FROM {self.table_name} WHERE `{column_name}` = %s"
        self.cursor.execute(query, (value,))
        rows = self.cursor.fetchall()
        column_names = [i[0] for i in self.cursor.description]
        df = pd.DataFrame(rows, columns=column_names)
        return df

    def delete_rows_by_id_range(self, start_id, end_id):
        primary_key = self._find_primary_key()
        if not primary_key:
            print("Primary key not found.")
            return

        query = f"DELETE FROM {self.table_name} WHERE `{primary_key}` BETWEEN %s AND %s"
        cursor = self.connection.cursor()
        try:
            cursor.execute(query, (start_id, end_id))
            self.connection.commit()
            print(f"Deleted rows from {primary_key} {start_id} to {end_id}.")
        finally:
            cursor.close()

    def delete_rows_by_column_value(self, column_name, value):
        query = f"DELETE FROM {self.table_name} WHERE `{column_name}` = %s"
        self.cursor.execute(query, (value,))
        self.connection.commit()
        print(f"Deleted rows where {column_name} = {value}.")

    def drop_table(self):
        cursor = self.connection.cursor()
        try:
            query = f"DROP TABLE IF EXISTS {self.table_name}"
            cursor.execute(query)
            self.connection.commit()
        finally:
            cursor.close()
        print(f"Table '{self.table_name}' has been dropped.")

    def add_column(self, column_name, data_type):
        query = f"ALTER TABLE {self.table_name} ADD COLUMN `{column_name}` {data_type}"
        cursor = self.connection.cursor()
        try:
            cursor.execute(query)
            self.connection.commit()
        finally:
            cursor.close()
        print(f"Column '{column_name}' of type '{data_type}' added to table '{self.table_name}'.")

    def delete_column(self, column_name):
        cursor = self.connection.cursor()
        try:
            query = f"ALTER TABLE {self.table_name} DROP COLUMN `{column_name}`"
            cursor.execute(query)
            self.connection.commit()
        finally:
            cursor.close()

    def count_rows(self):
        cursor = self.connection.cursor()
        try:
            cursor.execute(f"SELECT COUNT(*) FROM {self.table_name}")
            result = cursor.fetchone()
            count = result[0] if result else 0
        finally:
            cursor.close()
        print(f"Total rows in '{self.table_name}': {count}")
        return count

    def search_column_for_string(self, column_name, search_string):
        if column_name not in self.columns:
            print(f"Error: Column '{column_name}' does not exist in the table '{self.table_name}'.")
            return pd.DataFrame()

        query = f"SELECT * FROM {self.table_name} WHERE `{column_name}` LIKE %s"
        search_pattern = f"%{search_string}%"
        self.cursor.execute(query, (search_pattern,))
        rows = self.cursor.fetchall()
        column_names = [col[0] for col in self.cursor.description]
        df = pd.DataFrame(rows, columns=column_names)
        print(f"Found {len(df)} results for search string '{search_string}' in column '{column_name}'.")
        return df

    def search_column_for_int(self, column_name, search_int):
        if column_name not in self.columns:
            print(f"Error: Column '{column_name}' does not exist in the table '{self.table_name}'.")
            return pd.DataFrame()

        query = f"SELECT * FROM {self.table_name} WHERE `{column_name}` = %s"
        self.cursor.execute(query, (search_int,))
        rows = self.cursor.fetchall()
        column_names = [col[0] for col in self.cursor.description]
        df = pd.DataFrame(rows, columns=column_names)
        print(f"Found {len(df)} results for search integer '{search_int}' in column '{column_name}'.")
        return df

    def inner_join(self, other_table, join_column, other_join_column=None, select_columns='*', where_clause=''):
        if not other_join_column:
            other_join_column = join_column

        query = f"""
        SELECT {select_columns}
        FROM {self.table_name}
        INNER JOIN {other_table} ON {self.table_name}.`{join_column}` = {other_table}.`{other_join_column}`
        {where_clause}
        """
        cursor = self.connection.cursor()
        try:
            cursor.execute(query)
            rows = cursor.fetchall()
            column_names = [col[0] for col in cursor.description]
        finally:
            cursor.close()

        return pd.DataFrame(rows, columns=column_names)

    def import_from_csv(self, file_path, columns=None):
        df = pd.read_csv(file_path, header=0 if columns is None else None)
        if columns is not None:
            df.columns = columns
        self._bulk_insert_dataframe(df)

    def import_from_excel(self, file_path, columns=None):
        df = pd.read_excel(file_path, header=0 if columns is None else None)
        if columns is not None:
            df.columns = columns
        self._bulk_insert_dataframe(df)

    def _bulk_insert_dataframe(self, df):
        placeholders = ', '.join(['%s'] * len(df.columns))
        columns = ', '.join([f"`{column}`" for column in df.columns])
        query = f"INSERT INTO {self.table_name} ({columns}) VALUES ({placeholders})"
        data = df.to_records(index=False)

        cursor = self.connection.cursor()
        try:
            for record in data:
                cursor.execute(query, tuple(record))
            self.connection.commit()
        finally:
            cursor.close()

    def left_join(self, other_table, join_column, other_join_column=None, select_columns='*', where_clause=''):
        other_join_column = other_join_column or join_column
        query = f"""
        SELECT {select_columns}
        FROM {self.table_name}
        LEFT JOIN {other_table} ON {self.table_name}.`{join_column}` = {other_table}.`{other_join_column}`
        {where_clause}
        """
        return self._execute_query(query)

    def right_join(self, other_table, join_column, other_join_column=None, select_columns='*', where_clause=''):
        other_join_column = other_join_column or join_column
        query = f"""
        SELECT {select_columns}
        FROM {self.table_name}
        RIGHT JOIN {other_table} ON {self.table_name}.`{join_column}` = {other_table}.`{other_join_column}`
        {where_clause}
        """
        return self._execute_query(query)

    def cross_join(self, other_table, select_columns='*'):
        query = f"""
        SELECT {select_columns}
        FROM {self.table_name}
        CROSS JOIN {other_table}
        """
        return self._execute_query(query)

    def self_join(self, join_column, alias_one='a', alias_two='b', select_columns='*', where_clause=''):
        query = f"""
        SELECT {select_columns}
        FROM {self.table_name} AS {alias_one}
        JOIN {self.table_name} AS {alias_two} ON {alias_one}.`{join_column}` = {alias_two}.`{join_column}`
        {where_clause}
        """
        return self._execute_query(query)

    def _execute_query(self, query):
        cursor = self.connection.cursor()
        try:
            cursor.execute(query)
            rows = cursor.fetchall()
            column_names = [col[0] for col in cursor.description]
        finally:
            cursor.close()
        return pd.DataFrame(rows, columns=column_names)

    def execute_query(self, query):
        cursor = self.connection.cursor()
        try:
            cursor.execute(query)
            rows = cursor.fetchall()
            column_names = [col[0] for col in cursor.description]
        finally:
            cursor.close()
        return pd.DataFrame(rows, columns=column_names)

    def execute_query_with_params(self, query, params):
        cursor = self.connection.cursor()
        try:
            cursor.execute(query, params)
            rows = cursor.fetchall()
            column_names = [col[0] for col in cursor.description]
        finally:
            cursor.close()
        return pd.DataFrame(rows, columns=column_names)

    def plot_keyword_trends_index(self, keywords, start_date, end_date, text_column='full_text', date_column='date'):
        import pandas as pd
        from pandas import date_range

        all_months = pd.date_range(start=start_date, end=end_date, freq='MS').strftime('%Y-%m')
        month_index = pd.to_datetime(all_months)

        all_data = []
        for keyword in keywords:
            query = f"""
            SELECT DATE_FORMAT(`{date_column}`, '%Y-%m') AS month,
                   COUNT(*) AS count,
                   '{keyword}' AS keyword
            FROM {self.table_name}
            WHERE `{date_column}` BETWEEN %s AND %s
              AND MATCH(`{text_column}`) AGAINST(%s IN NATURAL LANGUAGE MODE)
            GROUP BY month
            ORDER BY STR_TO_DATE(month, '%Y-%m')
            """
            keyword_query = f'"{keyword}"'
            print("Executing:", query)
            print("With params:", (start_date, end_date, keyword_query))
            df = self.execute_query_with_params(query, (start_date, end_date, keyword_query))
            print("Result for", keyword, df)
            df['month'] = pd.to_datetime(df['month'], format='%Y-%m')
            all_data.append(df)

        if not all_data:
            print("No keyword matches found in the given period.")
            return pd.DataFrame(index=month_index, columns=keywords).fillna(0)

        result_df = pd.concat(all_data, ignore_index=True)
        pivot_df = result_df.pivot(index='month', columns='keyword', values='count').reindex(index=month_index).fillna(0).astype(int)

        fig, ax = plt.subplots(figsize=(10, 5))
        for keyword in keywords:
            if keyword in pivot_df.columns:
                ax.plot(pivot_df.index, pivot_df[keyword], marker='o', linestyle='-', label=keyword)

        ax.set_title('Monthly Keyword Frequency')
        ax.set_xlabel('Month')
        ax.set_ylabel('Frequency')
        ax.grid(True)
        ax.legend()
        fig.autofmt_xdate()
        plt.tight_layout()
        plt.show()
        return pivot_df

    def plot_keyword_trends(self, keywords, start_date, end_date, text_column='full_text', date_column='date'):
        import pandas as pd
        from datetime import datetime

        all_months = pd.date_range(start=start_date, end=end_date, freq='MS')
        results = {k: [] for k in keywords}
        month_labels = []

        for month_start in all_months:
            month_end = (month_start + pd.DateOffset(months=1)) - pd.DateOffset(days=1)
            month_label = month_start.strftime('%Y-%m')
            month_labels.append(month_start)

            query = f"""
            SELECT `{text_column}` FROM {self.table_name}
            WHERE `{date_column}` BETWEEN %s AND %s
            """
            df = self.execute_query_with_params(query, (month_start.strftime('%Y-%m-%d'), month_end.strftime('%Y-%m-%d')))

            full_text = ' '.join(df[text_column].dropna().astype(str)).lower()
            for k in keywords:
                count = full_text.count(k.lower())
                results[k].append(count)

        pivot_df = pd.DataFrame(results, index=month_labels)

        fig, ax = plt.subplots(figsize=(10, 5))
        for keyword in keywords:
            ax.plot(pivot_df.index, pivot_df[keyword], marker='o', linestyle='-', label=keyword)

        ax.set_title('Monthly Keyword Frequency (no fulltext index)')
        ax.set_xlabel('Month')
        ax.set_ylabel('Frequency')
        ax.grid(True)
        ax.legend()
        fig.autofmt_xdate()
        plt.tight_layout()

        return pivot_df

    def inspect_table_dates(self, limit=100):
        query = f"SELECT DISTINCT `date` FROM {self.table_name} ORDER BY `date` ASC LIMIT %s"
        df = self.execute_query_with_params(query, (limit,))
        print("[INFO] Уникальные даты в таблице:")
        print(df)
        return df

    def update_range(self, id_start, id_end, column_name, new_value):
        cursor = self.connection.cursor()
        try:
            query = f"UPDATE {self.table_name} SET `{column_name}` = %s WHERE `id` BETWEEN %s AND %s"
            cursor.execute(query, (new_value, id_start, id_end))
            self.connection.commit()
        finally:
            cursor.close()
        print(f"Updated records from ID {id_start} to {id_end} setting `{column_name}` to {new_value}.")

    def update_where(self, column_name, new_value, where_clause):
        cursor = self.connection.cursor()
        try:
            query = f"UPDATE {self.table_name} SET `{column_name}` = %s {where_clause}"
            cursor.execute(query, (new_value,))
            self.connection.commit()
        finally:
            cursor.close()
        print(f"Updated `{column_name}` to {new_value} where {where_clause}.")

    def select_where(self, where_clause, select_columns='*'):
        cursor = self.connection.cursor()
        try:
            query = f"SELECT {select_columns} FROM {self.table_name} {where_clause}"
            cursor.execute(query)
            rows = cursor.fetchall()
            column_names = [col[0] for col in cursor.description]
        finally:
            cursor.close()
        return pd.DataFrame(rows, columns=column_names)

    def delete_where(self, where_clause):
        cursor = self.connection.cursor()
        try:
            query = f"DELETE FROM {self.table_name} {where_clause}"
            cursor.execute(query)
            self.connection.commit()
        finally:
            cursor.close()
        print(f"Deleted rows {where_clause}.")

    def recreate_table(self):
        create_statement = self._fetch_create_statement()
        if not create_statement:
            print(f"Failed to fetch CREATE statement for the table '{self.table_name}'.")
            return

        self.drop_table()

        cursor = self.connection.cursor()
        try:
            cursor.execute(create_statement)
            self.connection.commit()
        finally:
            cursor.close()
        print(f"Table '{self.table_name}' was recreated successfully.")

    def _fetch_create_statement(self):
        cursor = self.connection.cursor()
        try:
            cursor.execute(f"SHOW CREATE TABLE {self.table_name}")
            result = cursor.fetchone()
            create_statement = result[1] if result else None
        finally:
            cursor.close()
        return create_statement

    def export_table_to_sql(self):
        create_statement = self._fetch_create_statement()
        if not create_statement:
            print(f"Failed to fetch CREATE statement for the table '{self.table_name}'.")
            return

        data = self.fetch_all()
        insert_statements = self._generate_insert_statements(data)

        sql_commands = f"{create_statement};\n\n{insert_statements}"

        timestamp = datetime.datetime.now().strftime('%Y-%m-%d_%H-%M-%S')
        filename = f"{self.table_name}_{timestamp}.sql"
        downloads_path = os.path.join(os.path.expanduser('~'), 'Downloads')
        if not os.path.exists(downloads_path):
            os.makedirs(downloads_path)
        file_path = os.path.join(downloads_path, filename)

        with open(file_path, 'w') as file:
            file.write(sql_commands)
        print(f"Table '{self.table_name}' exported to SQL file: {file_path}")

    def _generate_insert_statements(self, data):
        inserts = []
        for _, row in data.iterrows():
            columns = ', '.join([f"`{col}`" for col in data.columns])
            values = ', '.join(
                [f"'{SQLTable.escape_sql_string(val)}'" if isinstance(val, str) else str(val) for val in row])
            inserts.append(f"INSERT INTO `{self.table_name}` ({columns}) VALUES ({values});")
        return '\n'.join(inserts)

    @staticmethod
    def escape_sql_string(value):
        trans_table = {ord(','): None, ord(':'): None, ord('.'): None, ord('&'): None, ord('!'): None, ord('"'): None,
                       ord('?'): None, ord('\n'): None, ord('	'): None, ord('@'): None, ord("'"): None, ord("’"): None,
                       ord("Ö"): None}
        return value.translate(trans_table)

    def add_foreign_key(self, column_name, referenced_table, referenced_column, constraint_name=None):
        if column_name not in self.columns:
            print(f"Error: Column '{column_name}' does not exist in table '{self.table_name}'. Operation aborted.")
            return False

        if not self._check_column_exists(referenced_table, referenced_column):
            print(f"Error: Referenced column '{referenced_column}' does not exist in table '{referenced_table}'. Operation aborted.")
            return False

        if not constraint_name:
            constraint_name = f"fk_{self.table_name}_{column_name}_{referenced_table}_{referenced_column}"

        sql = f"""
        ALTER TABLE {self.table_name}
        ADD CONSTRAINT `{constraint_name}`
        FOREIGN KEY (`{column_name}`) REFERENCES `{referenced_table}`(`{referenced_column}`);
        """
        cursor = self.connection.cursor()
        try:
            cursor.execute(sql)
            self.connection.commit()
            print(f"Foreign key added: {column_name} -> {referenced_table}({referenced_column})")
            return True
        except Exception as e:
            print(f"Failed to add foreign key: {str(e)}")
            return False
        finally:
            cursor.close()

    def _check_column_exists(self, table_name, column_name):
        cursor = self.connection.cursor()
        try:
            cursor.execute(f"SHOW COLUMNS FROM `{table_name}` LIKE '{column_name}'")
            return cursor.fetchone() is not None
        finally:
            cursor.close()

    def print_table_info(self):
        print(f"Information for table '{self.table_name}':")
        print("\nTable Structure:")
        self.print_table_structure()
        num_rows = self.count_rows()
        print(f"\nNumber of Rows: {num_rows}")
        print(f"\nDatabase Name: {self.db_config['database']}")
        print("\nForeign Keys:")
        self.print_foreign_keys()

    def print_table_structure(self):
        cursor = self.connection.cursor()
        try:
            cursor.execute(f"DESCRIBE {self.table_name}")
            columns = cursor.fetchall()
            for column in columns:
                print(f"{column[0]} ({column[1]})")
        finally:
            cursor.close()

    def print_foreign_keys(self):
        cursor = self.connection.cursor()
        try:
            cursor.execute(f"""
            SELECT CONSTRAINT_NAME, COLUMN_NAME, REFERENCED_TABLE_NAME, REFERENCED_COLUMN_NAME
            FROM INFORMATION_SCHEMA.KEY_COLUMN_USAGE
            WHERE TABLE_NAME = '{self.table_name}' AND TABLE_SCHEMA = '{self.db_config['database']}'
            AND REFERENCED_TABLE_NAME IS NOT NULL;
            """)
            fks = cursor.fetchall()
            if fks:
                for fk in fks:
                    print(f"{fk[0]}: {fk[1]} references {fk[2]}({fk[3]})")
            else:
                print("No foreign keys.")
        finally:
            cursor.close()

    def check_fulltext_index(self, columns):
        query = f"SHOW INDEX FROM {self.table_name};"
        cursor = self.connection.cursor()
        cursor.execute(query)
        indexes = cursor.fetchall()

        index_columns = {}
        for index in indexes:
            index_name = index[2]
            column_name = index[4]
            index_type = index[10]

            if index_type == 'FULLTEXT':
                if index_name not in index_columns:
                    index_columns[index_name] = []
                index_columns[index_name].append(column_name)

        for index_name, index_col_list in index_columns.items():
            if all(col in index_col_list for col in columns):
                print(f"Полнотекстовый индекс '{index_name}' найден для столбцов: {', '.join(columns)}.")
                return True

        print(f"Полнотекстовый индекс для столбцов: {', '.join(columns)} не найден.")
        return False

    def search_fulltext(self, columns, keyword):
        if self.check_fulltext_index(columns):
            column_str = ", ".join(columns)
            query = f"""
            SELECT {column_str}
            FROM {self.table_name}
            WHERE MATCH({column_str}) AGAINST(%s IN NATURAL LANGUAGE MODE);
            """
            cursor = self.connection.cursor()
            cursor.execute(query, (keyword,))
            results = cursor.fetchall()

            if results:
                for row in results:
                    print(row)
            else:
                print("По вашему запросу ничего не найдено.")
        else:
            print("Полнотекстовый индекс отсутствует, поиск невозможен.")

    def fetch_all_as_json(self):
        query = f"SELECT * FROM {self.table_name}"
        df = self._execute_query(query)
        records = df.to_dict(orient='records')
        json_objects = [json.dumps(record) for record in records]
        return json_objects

    def fetch_filtered_as_json(self, where_clause='', columns='*'):
        query = f"SELECT {columns} FROM {self.table_name} {where_clause}"
        df = self._execute_query(query)
        records = df.to_dict(orient='records')
        json_objects = [json.dumps(record) for record in records]
        return json_objects

    def insert_json_objects_as_string(self, json_objects, column_name):
        query = f"INSERT INTO {self.table_name} ({column_name}) VALUES (%s)"
        cursor = self.connection.cursor()
        try:
            for json_object in json_objects:
                if isinstance(json_object, dict):
                    json_str = json.dumps(json_object)
                else:
                    json_str = json_object
                cursor.execute(query, (json_str,))
            self.connection.commit()
        finally:
            cursor.close()

    def update_columns_from_json(self, json_column, id_column, columns_to_extract):
        query = f"SELECT {id_column}, {json_column} FROM {self.table_name}"
        rows = self._execute_query(query)

        set_clause = ', '.join([f"{col} = %s" for col in columns_to_extract])
        update_query = f"UPDATE {self.table_name} SET {set_clause} WHERE {id_column} = %s"

        cursor = self.connection.cursor()

        try:
            for row in rows.itertuples(index=False):
                record_id = getattr(row, id_column)
                json_data = getattr(row, json_column)

                try:
                    json_obj = json.loads(json_data)
                except json.JSONDecodeError:
                    print(f"Ошибка декодирования JSON для записи с ID {record_id}")
                    continue

                values_to_update = [json_obj.get(col) for col in columns_to_extract]

                if None in values_to_update:
                    print(f"Не все данные найдены для записи с ID {record_id}, пропускаем.")
                    continue

                cursor.execute(update_query, (*values_to_update, record_id))

            self.connection.commit()
        except Exception as e:
            self.connection.rollback()
            print(f"Ошибка при обновлении данных: {e}")
        finally:
            cursor.close()

    def push_list(self, tags_list, column):
        for tag in tags_list:
            existing_tag_df = self.select_where(f"WHERE '{column}' = '{tag}'")

            if existing_tag_df.empty:
                self.insert_row({f'{column}': tag})
            else:
                print(f"Tag '{column}' already exists, skipping.")

    def execute_update(self, query, params):
        self.cursor.executemany(query, params)
        self.connection.commit()

    def update_keyword_counts(self, keywords_table, articles_table):
        try:
            keywords = keywords_table.fetch_all()
            if keywords.empty:
                print("No keywords found.")
                return

            keyword_counts = []

            for _, row in keywords.iterrows():
                keyword_id = row['id']
                keyword_text = row['keyword']

                query = f"""
                    SELECT COUNT(*) AS count
                    FROM {articles_table.table_name}
                    WHERE MATCH(info) AGAINST(%s IN NATURAL LANGUAGE MODE);
                    """
                self.cursor.execute(query, (keyword_text,))
                result = self.cursor.fetchone()

                count = result[0] if result else 0

                print(f"Keyword ID: {keyword_id}, Count: {count}")

                keyword_counts.append((count, keyword_id))

            print("Keyword counts to update:", keyword_counts)

            update_query = "UPDATE keywords SET count = %s WHERE id = %s"
            keywords_table.execute_update(update_query, keyword_counts)

            self.connection.commit()

            self.cursor.execute("SELECT ROW_COUNT()")
            updated_rows = self.cursor.fetchone()[0]
            print(f"Rows updated: {updated_rows}")

            print(f"Updated counts for {len(keyword_counts)} keywords.")

        except mysql.connector.Error as err:
            print(f"Error: {err}")
            self.connection.rollback()

    def __del__(self):
        try:
            if self.cursor is not None:
                self.cursor.close()
            if self.connection is not None:
                self.connection.close()
        except ReferenceError:
            pass
        except Exception as e:
            print(f"Error closing database resources: {e}")


# Example usage:

db_config = {
    'user': 'j1498375',
    'password': 'b5f!g9Lemsyh',
    'host': 'srv48-h-st.jino.ru',
    'database': 'j1498375_test1'
}

table = SQLTable(db_config, 'mwj_combined')
temp = table.plot_keyword_trends(['Lockheed Martin', 'BAE Systems', 'Thales', 'Mercury Systems'], '2021-01-01', '2023-01-31')
temp = table.plot_keyword_trends_index(['C-Band', 'K-Band', 'X-Band', 'S-Band', 'L-Band'], '2021-01-01', '2023-01-31')
temp = table.plot_keyword_trends_index(['High Throughput Satellite', 'phased-array HPA', 'GaN-on-SiC HEMT', 'GaN'], '2021-01-01', '2023-01-31')