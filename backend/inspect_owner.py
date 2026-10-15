import sqlite3
con = sqlite3.connect('medha.db')
cur = con.cursor()
print('passports:')
for r in cur.execute('select task_id, user_id, identity, role, title from task_passports order by task_id').fetchall():
    print(r)
print('conversations:')
for r in cur.execute('select id, user_id, title from conversations order by id').fetchall():
    print(r)
print('audit events:')
for r in cur.execute('select id, event_type, user_id, identity from audit_events order by id').fetchall():
    print(r)
