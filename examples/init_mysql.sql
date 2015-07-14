CREATE DATABASE storage;
USE storage;
CREATE TABLE `$TABLE_NAME` (   `date` datetime DEFAULT NULL,   `path` text,   `value` float DEFAULT NULL );
GRANT USAGE ON *.* TO '$REPORTING_USERNAME'@'%' IDENTIFIED BY '$PASSWORD';
GRANT ALL PRIVILEGES ON `storage`.* TO '$REPORTING_USERNAME'@'%';
GRANT SELECT ON `nova`.`instance_types` TO '$REPORTING_USERNAME'@'%';
GRANT SELECT ON `nova`.`instances` TO '$REPORTING_USERNAME'@'%';
CREATE TABLE `${CLOUD}_object` (   `date` datetime DEFAULT NULL,   `username` text, `tenant_name` text, `value` float DEFAULT NULL );
