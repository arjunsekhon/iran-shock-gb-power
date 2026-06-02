-- Athena external tables for the Iran-shock project (Stage 3).
-- Run in the `iran_shock` workgroup, `iran_shock` database.
-- Statements run ONE AT A TIME in the Athena editor (Athena rejects multiple per run).
-- LOCATION is always a folder; Athena reads every file in it.
-- All-string load mirrors DuckDB's all_varchar=true; the views do the casts.

-- 1. database
CREATE DATABASE IF NOT EXISTS iran_shock;

-- 2. GDELT: 61 string columns + a `date` partition. Tab-separated.
CREATE EXTERNAL TABLE IF NOT EXISTS gdelt (
  globaleventid string, day string, monthyear string, year string, fractiondate string,
  actor1code string, actor1name string, actor1countrycode string, actor1knowngroupcode string, actor1ethniccode string,
  actor1religion1code string, actor1religion2code string, actor1type1code string, actor1type2code string, actor1type3code string,
  actor2code string, actor2name string, actor2countrycode string, actor2knowngroupcode string, actor2ethniccode string,
  actor2religion1code string, actor2religion2code string, actor2type1code string, actor2type2code string, actor2type3code string,
  isrootevent string, eventcode string, eventbasecode string, eventrootcode string, quadclass string,
  goldsteinscale string, nummentions string, numsources string, numarticles string, avgtone string,
  actor1geo_type string, actor1geo_fullname string, actor1geo_countrycode string, actor1geo_adm1code string, actor1geo_adm2code string,
  actor1geo_lat string, actor1geo_long string, actor1geo_featureid string,
  actor2geo_type string, actor2geo_fullname string, actor2geo_countrycode string, actor2geo_adm1code string, actor2geo_adm2code string,
  actor2geo_lat string, actor2geo_long string, actor2geo_featureid string,
  actiongeo_type string, actiongeo_fullname string, actiongeo_countrycode string, actiongeo_adm1code string, actiongeo_adm2code string,
  actiongeo_lat string, actiongeo_long string, actiongeo_featureid string,
  dateadded string, sourceurl string
)
PARTITIONED BY (date string)
ROW FORMAT DELIMITED FIELDS TERMINATED BY '\t'
LOCATION 's3://iran-shock-gb-power-477170636359/raw/gdelt/';

-- 3. register the date=YYYY-MM-DD/ partitions (run after the gdelt table exists)
MSCK REPAIR TABLE gdelt;

-- 4. price tables — one subfolder per table (matches pipeline/ingest_prices_s3.py)
CREATE EXTERNAL TABLE IF NOT EXISTS brent (price_date date, brent_close double)
ROW FORMAT DELIMITED FIELDS TERMINATED BY ','
LOCATION 's3://iran-shock-gb-power-477170636359/raw/prices/brent/'
TBLPROPERTIES ('skip.header.line.count'='1');

CREATE EXTERNAL TABLE IF NOT EXISTS gb_power (price_date date, gb_power_avg double)
ROW FORMAT DELIMITED FIELDS TERMINATED BY ','
LOCATION 's3://iran-shock-gb-power-477170636359/raw/prices/gb_power/'
TBLPROPERTIES ('skip.header.line.count'='1');

CREATE EXTERNAL TABLE IF NOT EXISTS ttf (price_date date, ttf_close double)
ROW FORMAT DELIMITED FIELDS TERMINATED BY ','
LOCATION 's3://iran-shock-gb-power-477170636359/raw/prices/ttf/'
TBLPROPERTIES ('skip.header.line.count'='1');

CREATE EXTERNAL TABLE IF NOT EXISTS gb_gen_mix (
    price_date date, total_mwh double,
    gas_share_pct double, renewables_share_pct double,
    nuclear_share_pct double, biomass_share_pct double,
    coal_oil_share_pct double, pumped_storage_share_pct double
)
ROW FORMAT DELIMITED FIELDS TERMINATED BY ','
LOCATION 's3://iran-shock-gb-power-477170636359/raw/prices/gb_gen_mix/'
TBLPROPERTIES ('skip.header.line.count'='1');

CREATE EXTERNAL TABLE IF NOT EXISTS timeline (event_date date, label string, description string, source_url string)
ROW FORMAT DELIMITED FIELDS TERMINATED BY ','
LOCATION 's3://iran-shock-gb-power-477170636359/raw/events/'
TBLPROPERTIES ('skip.header.line.count'='1');
