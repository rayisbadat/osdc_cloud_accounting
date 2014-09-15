CREATE DATABASE storage_use;
USE storage_use;
CREATE TABLE `$TABLE_NAME` (   `date` datetime DEFAULT NULL,   `path` text,   `value` float DEFAULT NULL );
GRANT USAGE ON *.* TO '$REPORTING_USERNAME'@'%' IDENTIFIED BY '$PASSWORD';
GRANT ALL PRIVILEGES ON `storage_use`.* TO '$REPORTING_USERNAME'@'%';
GRANT SELECT ON `nova`.`instance_types` TO '$REPORTING_USERNAME'@'%';
GRANT SELECT ON `nova`.`instances` TO '$REPORTING_USERNAME'@'%';
