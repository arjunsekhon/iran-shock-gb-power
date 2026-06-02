"""GDELT 2.0 Event table — the 61 columns IN ORDER (Event Codebook V2.0).
No header in the files, so this list IS the schema."""

EVENT_COLUMNS = [
    "GlobalEventID",
    "Day",
    "MonthYear",
    "Year",
    "FractionDate",
    "Actor1Code",
    "Actor1Name",
    "Actor1CountryCode",
    "Actor1KnownGroupCode",
    "Actor1EthnicCode",
    "Actor1Religion1Code",
    "Actor1Religion2Code",
    "Actor1Type1Code",
    "Actor1Type2Code",
    "Actor1Type3Code",
    "Actor2Code",
    "Actor2Name",
    "Actor2CountryCode",
    "Actor2KnownGroupCode",
    "Actor2EthnicCode",
    "Actor2Religion1Code",
    "Actor2Religion2Code",
    "Actor2Type1Code",
    "Actor2Type2Code",
    "Actor2Type3Code",
    "IsRootEvent",
    "EventCode",
    "EventBaseCode",
    "EventRootCode",
    "QuadClass",
    "GoldsteinScale",
    "NumMentions",
    "NumSources",
    "NumArticles",
    "AvgTone",
    "Actor1Geo_Type",
    "Actor1Geo_Fullname",
    "Actor1Geo_CountryCode",
    "Actor1Geo_ADM1Code",
    "Actor1Geo_ADM2Code",
    "Actor1Geo_Lat",
    "Actor1Geo_Long",
    "Actor1Geo_FeatureID",
    "Actor2Geo_Type",
    "Actor2Geo_Fullname",
    "Actor2Geo_CountryCode",
    "Actor2Geo_ADM1Code",
    "Actor2Geo_ADM2Code",
    "Actor2Geo_Lat",
    "Actor2Geo_Long",
    "Actor2Geo_FeatureID",
    "ActionGeo_Type",
    "ActionGeo_Fullname",
    "ActionGeo_CountryCode",
    "ActionGeo_ADM1Code",
    "ActionGeo_ADM2Code",
    "ActionGeo_Lat",
    "ActionGeo_Long",
    "ActionGeo_FeatureID",
    "DATEADDED",
    "SOURCEURL",
]
assert len(EVENT_COLUMNS) == 61
CODE_COLUMNS = [
    "EventCode",
    "EventBaseCode",
    "EventRootCode",
]  # zero-leading -> read as strings


# GDELT GKG v2 — 27 columns in order.
# Note: GDELT field 2 is "DATE" but DuckDB treats `date` as a reserved type
# keyword, so we rename to `gkg_datestamp` for safe SQL usage.
GKG_COLUMNS = [
    "GKGRECORDID",
    "gkg_datestamp",
    "SourceCollectionIdentifier",
    "SourceCommonName",
    "DocumentIdentifier",  # the article URL
    "V1Counts",
    "V21Counts",
    "V1Themes",  # we filter at ingest on this (V1 themes, simpler list)
    "V2EnhancedThemes",  # richer, includes character offsets
    "V1Locations",
    "V2EnhancedLocations",  # full lat/lon + FIPS codes
    "V1Persons",
    "V2EnhancedPersons",
    "V1Organizations",
    "V2EnhancedOrganizations",
    "V2Tone",  # 6-part: tone,positive,negative,polarity,activity,self,wordcount
    "V2EnhancedDates",
    "V21GCAM",  # ~2,300 dimensions: c2.1:25,c2.10:29,...
    "V21SharingImage",
    "V21RelatedImages",
    "V21SocialImageEmbeds",
    "V21SocialVideoEmbeds",
    "V21Quotations",
    "V21AllNames",
    "V21Amounts",
    "V21TranslationInfo",
    "V2ExtrasXML",
]
assert len(GKG_COLUMNS) == 27
