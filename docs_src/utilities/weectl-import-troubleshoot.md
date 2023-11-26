## Dealing with import failures {#import_failures}

Sometimes bad things happen during an import.

If errors were encountered, or if you suspect that the WeeWX database has 
been contaminated with incorrect data, here are some things you can try to 
fix things up.

* Manually delete the contaminated data. Use SQL commands to manipulate 
  the data in the WeeWX archive database. The simplicity of this process 
  will depend on your ability to use SQL, the amount of data imported, and 
  whether the imported data was dispersed amongst existing. Once 
  contaminated data have been removed the daily summary tables will need 
  to be rebuilt using the `weectl database rebuild-daily` utility.

* Delete the database and start over. For SQLite, simply delete the 
  database file. For MySQL, drop the database. Then try the import again.

    !!! Warning
        Deleting the database file or dropping the database will result in 
        all data in the database being lost.

* If the above steps are not appropriate the database should be restored 
  from backup. You did make a backup before starting the import?
