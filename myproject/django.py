import sqlite3

connection_obj = sqlite3.connect('databasename.db')
cursor_obj = connection_obj.cursor()

# curd operation.....

# cursor close
connection_obj.commit()

# close of connection
connection_obj.close()


connection_obj.execute("""
CREATE TABLE  NAME (
Email varchar(255),
Name varchar(50),
Score int
);""")


connection_obj.execute("""
INSERT INTO test(Email,Name,Score)VALUE """)


#All The Data 
output=cursor_obj.fetchall()

#Read Some Rows
cursor_obj.fetchmany(size)


#Read only one row
cursor_obj.fetchone()







# migrate database

# python manage.py makemigration
# python manage.py migrate


# python manage.py shell
