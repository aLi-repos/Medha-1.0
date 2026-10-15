import sqlite3
con = sqlite3.connect('medha.db')
cur = con.cursor()
tables = [r[0] for r in cur.execute('select name from sqlite_master where type=\'table\' order by name').fetchall()]
print('TABLES:', tables)
print('USER COLUMNS:', [r[1] for r in cur.execute('pragma table_info(users)').fetchall()])
for row in cur.execute('select id, user_id, username, role from users order by id').fetchall():
    print(row)
