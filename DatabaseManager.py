import csv
import io
from typing import List, Dict, Any, Optional

from sqlalchemy import (
    create_engine,
    MetaData,
    Table,
    select,
    insert,
    delete,
    text,
    desc,
    asc,
)
from sqlalchemy.engine import Engine


class DatabaseManager:
    """
    Класс для взаимодействия с реляционной базой данных через SQLAlchemy Core.
    Позволяет выполнять запросы к таблицам, модифицировать структуру,
    удалять данные и таблицы, а также экспортировать/импортировать в CSV.
    """

    def __init__(self, connection_string: str):
        """
        Инициализация движка и объекта MetaData.

        :param connection_string: строка подключения (например,
                                  "postgresql://user:pass@localhost/dbname")
        """
        self.engine: Engine = create_engine(connection_string, echo=False)
        self.metadata: MetaData = MetaData()

    def _get_table(self, table_name: str) -> Table:
        """
        Вспомогательный метод: загружает схему таблицы из базы данных,
        если она ещё не отражена в self.metadata.

        :param table_name: имя таблицы
        :return: объект Table, готовый к использованию
        """
        if table_name not in self.metadata.tables:
            # Автоматически отражаем существующую таблицу
            self.metadata.reflect(bind=self.engine, only=[table_name])
        return self.metadata.tables[table_name]

    # ------------------------------------------------------------------
    # 1. Вывод конкретного столбца в порядке убывания или возрастания
    # ------------------------------------------------------------------
    def get_column_sorted(
        self,
        table_name: str,
        column_name: str,
        order: str = "asc",
        limit: Optional[int] = None,
    ) -> List[Any]:
        """
        Возвращает значения указанного столбца, отсортированные по этому же столбцу.

        :param table_name: имя таблицы
        :param column_name: имя столбца
        :param order:   направление сортировки: 'asc' (по возрастанию)
                        или 'desc' (по убыванию)
        :param limit:   максимальное количество возвращаемых строк (None – все)
        :return:        список значений столбца
        """
        table = self._get_table(table_name)
        column = table.c[column_name]

        # Определяем направление сортировки
        order_func = asc if order.lower() == "asc" else desc

        # Формируем запрос SELECT column_name FROM table ORDER BY column_name ...
        stmt = select(column).order_by(order_func(column))
        if limit is not None:
            stmt = stmt.limit(limit)

        with self.engine.connect() as conn:
            result = conn.execute(stmt)
            # Извлекаем значения (каждая строка – кортеж из одного элемента)
            return [row[0] for row in result]

    # ------------------------------------------------------------------
    # 2. Вывод диапазона строк по айди
    # ------------------------------------------------------------------
    def get_rows_by_id_range(
        self, table_name: str, start_id: int, end_id: int
    ) -> List[Dict[str, Any]]:
        """
        Возвращает строки таблицы, у которых идентификатор лежит в диапазоне [start_id, end_id].

        Предполагается, что в таблице есть столбец 'id'.

        :param table_name: имя таблицы
        :param start_id:   нижняя граница (включительно)
        :param end_id:     верхняя граница (включительно)
        :return:           список словарей (каждый словарь – строка)
        """
        table = self._get_table(table_name)
        id_col = table.c["id"]

        stmt = select(table).where(id_col.between(start_id, end_id))

        with self.engine.connect() as conn:
            result = conn.execute(stmt)
            # result.mappings() позволяет сразу получить словари
            return [dict(row) for row in result.mappings()]

    # ------------------------------------------------------------------
    # 3. Удаление диапазона строк по айди
    # ------------------------------------------------------------------
    def delete_rows_by_id_range(
        self, table_name: str, start_id: int, end_id: int
    ) -> int:
        """
        Удаляет строки, попадающие в заданный диапазон идентификаторов.

        :param table_name: имя таблицы
        :param start_id:   нижняя граница (включительно)
        :param end_id:     верхняя граница (включительно)
        :return:           количество удалённых строк
        """
        table = self._get_table(table_name)
        id_col = table.c["id"]

        stmt = delete(table).where(id_col.between(start_id, end_id))

        with self.engine.connect() as conn:
            result = conn.execute(stmt)
            conn.commit()  # обязательно фиксируем транзакцию
            return result.rowcount

    # ------------------------------------------------------------------
    # 4. Вывод структуры таблицы
    # ------------------------------------------------------------------
    def get_table_structure(self, table_name: str) -> Dict[str, str]:
        """
        Возвращает словарь {имя_столбца: тип_данных} для заданной таблицы.

        :param table_name: имя таблицы
        :return:           словарь с именами столбцов и их SQL-типами
        """
        table = self._get_table(table_name)
        return {col.name: str(col.type) for col in table.columns}

    # ------------------------------------------------------------------
    # 5. Вывод строки, содержащей конкретное значение в конкретном столбце
    # ------------------------------------------------------------------
    def find_rows_by_column_value(
        self, table_name: str, column_name: str, value: Any
    ) -> List[Dict[str, Any]]:
        """
        Возвращает все строки, в которых указанный столбец равен заданному значению.

        :param table_name: имя таблицы
        :param column_name: имя столбца
        :param value:       искомое значение (автоматическая параметризация)
        :return:            список словарей
        """
        table = self._get_table(table_name)
        column = table.c[column_name]

        stmt = select(table).where(column == value)

        with self.engine.connect() as conn:
            result = conn.execute(stmt)
            return [dict(row) for row in result.mappings()]

    # ------------------------------------------------------------------
    # 6. Удаление таблицы
    # ------------------------------------------------------------------
    def drop_table(self, table_name: str) -> None:
        """
        Полностью удаляет таблицу из базы данных.

        :param table_name: имя удаляемой таблицы
        """
        # Используем чистый DDL-запрос, так как Table.drop() требует наличие
        # объекта Table, зарегистрированного в метаданных с полной схемой.
        # Мы же хотим быстро удалить таблицу, даже если она только что
        # отражена через _get_table.
        with self.engine.connect() as conn:
            conn.execute(text(f"DROP TABLE IF EXISTS {table_name} CASCADE"))
            conn.commit()

        # Если таблица была в metadata – убираем её
        if table_name in self.metadata.tables:
            self.metadata.remove(self.metadata.tables[table_name])

    # ------------------------------------------------------------------
    # 7. Добавление и удаление нового столбца
    # ------------------------------------------------------------------
    def add_column(
        self, table_name: str, column_name: str, column_type: str
    ) -> None:
        """
        Добавляет новый столбец к существующей таблице.

        :param table_name:  имя таблицы
        :param column_name: имя нового столбца
        :param column_type: SQL-тип столбца (например "VARCHAR(255)", "INTEGER")
        """
        # Так как синтаксис ALTER TABLE может различаться, используем raw DDL.
        # Пользователь сам передаёт корректный тип в строковом виде.
        ddl = f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_type}"
        with self.engine.connect() as conn:
            conn.execute(text(ddl))
            conn.commit()

        # Обновляем метаданные, чтобы отразить новую структуру
        self.metadata.clear()  # проще всего очистить и отразить заново при следующем обращении

    def remove_column(self, table_name: str, column_name: str) -> None:
        """
        Удаляет существующий столбец из таблицы.

        :param table_name:  имя таблицы
        :param column_name: имя удаляемого столбца
        """
        ddl = f"ALTER TABLE {table_name} DROP COLUMN {column_name}"
        with self.engine.connect() as conn:
            conn.execute(text(ddl))
            conn.commit()

        self.metadata.clear()

    # ------------------------------------------------------------------
    # 8. Экспорт таблицы в CSV
    # ------------------------------------------------------------------
    def export_to_csv(self, table_name: str, file_path: str) -> None:
        """
        Сохраняет содержимое таблицы в файл CSV.

        :param table_name: имя таблицы
        :param file_path:  путь для сохранения CSV-файла
        """
        table = self._get_table(table_name)
        stmt = select(table)

        with self.engine.connect() as conn:
            result = conn.execute(stmt)
            # Получаем имена столбцов из результата (порядок гарантирован)
            columns = result.keys()
            rows = result.fetchall()

        with open(file_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(columns)          # заголовок
            writer.writerows(rows)            # данные

    # ------------------------------------------------------------------
    # 9. Импорт таблицы из CSV
    # ------------------------------------------------------------------
    def import_from_csv(self, table_name: str, file_path: str) -> int:
        """
        Загружает данные из CSV-файла в таблицу. Столбцы в CSV должны
        соответствовать столбцам таблицы.

        :param table_name: имя таблицы
        :param file_path:  путь к CSV-файлу
        :return:           количество вставленных строк
        """
        table = self._get_table(table_name)

        # Читаем CSV
        with open(file_path, "r", newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            rows = list(reader)

        if not rows:
            return 0

        # Массовая вставка
        with self.engine.connect() as conn:
            # Проверяем, что заголовки CSV совпадают с колонками таблицы
            csv_cols = rows[0].keys()
            # Строим INSERT-запрос
            stmt = insert(table).values(list_of_dicts=rows)
            result = conn.execute(stmt)
            conn.commit()
            return result.rowcount