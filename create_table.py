import psycopg2
conn = psycopg2.connect("dbname=smdr user=postgres")
cur = conn.cursor()

cur.execute(\
"CREATE TABLE freesmdr (\
  \"idfreesmdr\" bigserial,\
  \"call_start\" timestamp DEFAULT NULL,\
  \"call_duration\" time DEFAULT NULL,\
  \"ring_duration\" time DEFAULT NULL,\
  \"caller\" varchar(255) DEFAULT NULL,\
  \"direction\" varchar(255) DEFAULT NULL,\
  \"called_number\" varchar(255) DEFAULT NULL,\
  \"dialled_number\" varchar(255) DEFAULT NULL,\
  \"account\" varchar(255) DEFAULT NULL,\
  \"is_internal\" smallint DEFAULT NULL,\
  \"call_id\" int DEFAULT NULL,\
  \"continuation\" smallint DEFAULT NULL,\
  \"party1device\" char(5) DEFAULT NULL,\
  \"party1name\" varchar(255) DEFAULT NULL,\
  \"party2device\" char(5) DEFAULT NULL,\
  \"party2name\" varchar(255) DEFAULT NULL,\
  \"hold_time\" time DEFAULT NULL,\
  \"park_time\" time DEFAULT NULL,\
  \"authvalid\" varchar(255) DEFAULT NULL,\
  \"authcode\" varchar(255) DEFAULT NULL,\
  \"user_charged\" varchar(255) DEFAULT NULL,\
  \"call_charge\" varchar(255) DEFAULT NULL,\
  \"currency\" varchar(255) DEFAULT NULL,\
  \"amount_change\" varchar(255) DEFAULT NULL,\
  \"call_units\" varchar(255) DEFAULT NULL,\
  \"units_change\" varchar(255) DEFAULT NULL,\
  \"cost_per_unit\" varchar(255) DEFAULT NULL,\
  \"markup\" varchar(255) DEFAULT NULL,\
  PRIMARY KEY (\"idfreesmdr\")\
);")

# Make the changes to the database persistent
conn.commit()

# Close communication with the database
cur.close()
conn.close()


#run as sudo
#create /var/log/freesmdr
