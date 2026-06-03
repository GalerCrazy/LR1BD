from DatabaseManager import DatabaseManager
from SQLTable1 import SQLTable
from config import *

TableName = "jew"
T = SQLTable(Config, TableName)
M = DatabaseManager(T)