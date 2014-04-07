CREATE DATABASE storage_use;
CREATE TABLE `PDCv2` (   `date` datetime DEFAULT NULL,   `path` text,   `value` float DEFAULT NULL );
GRANT USAGE ON *.* TO '$REPORTING_USERNAME'@'%' IDENTIFIED BY '$PASSWORD';
GRANT ALL PRIVILEGES ON `storage_use`.* TO '$REPORTING_USERNAME'@'%';
GRANT SELECT ON `nova`.`instance_types` TO '$REPORTING_USERNAME'@'%';
GRANT SELECT ON `nova`.`instances` TO '$REPORTING_USERNAME'@'%';
