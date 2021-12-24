#!/usr/bin/env bash
#
# Shell script to set up the MySQL database for testing
#
# It creates three users:
#
# 1. User: weewx
#    Password: weewx
# 2. User: weewx1
#    Password: weewx1
# 3. User: weewx2
#    Password: weewx2
#
# NB: user weewx2 has more restrictive permissions than user weewx1
#
echo "Give the root password when prompted->"
# Use the TCP protocol so we can connect to a Docker container running MySQL.
mysql --force --protocol=tcp -u root -p << EOF
drop user if exists 'weewx';
drop user if exists 'weewx1';
drop user if exists 'weewx2';
create user 'weewx' identified by 'weewx';
create user 'weewx1' identified by 'weewx1';
create user 'weewx2' identified by 'weewx2';
grant select, update, create, delete, drop, insert on test.*           to 'weewx';
grant select, update, create, delete, drop, insert on test_alt_weewx.* to 'weewx';
grant select, update, create, delete, drop, insert on test_alt_weewx.* to 'weewx1';
grant select, update, create, delete, drop, insert on test_scratch.*   to 'weewx';
grant select, update, create, delete, drop, insert on test_sim.*       to 'weewx';
grant select, update, create, delete, drop, insert on test_sim.*       to 'weewx1';
grant select, update, create, delete, drop, insert on test_weedb.*     to 'weewx';
grant select, update, create, delete, drop, insert on test_weedb.*     to 'weewx1';
grant select, update, create, delete, drop, insert on test_weewx.*     to 'weewx';
grant select, update, create, delete, drop, insert on test_weewx.*     to 'weewx1';
grant select, update, create, delete, drop, insert on test_weewx1.*    to 'weewx';
grant select, update, create, delete, drop, insert on test_weewx2.*    to 'weewx';
grant select, update, create, delete, drop, insert on test_weewx1.*    to 'weewx1';
grant select, update, create, delete, drop, insert on test_weewx2.*    to 'weewx1';
grant select, update, create, delete, drop, insert on test_weewx2.*    to 'weewx2';
grant select, update, create, delete, drop, insert on weewx.*          to 'weewx';
EOF
if [ $? -eq 0 ]; then
    echo "Finished setting up MySQL."
else
    echo "Problems setting up MySQL"
fi
