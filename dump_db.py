import sqlite3

# 1. Connect to the database (or create it if it doesn't exist)
conn = sqlite3.connect('highs.db', detect_types=sqlite3.PARSE_DECLTYPES)

# 2. Create a cursor object
cursor = conn.cursor()

# # 3. Execute a SELECT query
# cursor.execute("SELECT * FROM highs")  # Replace 'users' with your table name

# # 4. Fetch results
# rows = cursor.fetchall()

# # 5. Iterate and print results
# for row in rows:
    # print(row)

cursor.execute("PRAGMA table_info(highs)")  # Replace 'users' with your table name
columns = cursor.fetchall()

column_names = [col[1] for col in columns]  # col[1] is the column name

print(column_names)

# 6. Close the connection
conn.close()

