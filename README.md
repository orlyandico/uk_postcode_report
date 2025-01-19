# UK Postcode Report

NOTE: This tool scrapes data from streetcheck.co.uk. Please ensure you comply with their terms of service and implement appropriate rate limiting when using this code.

Python script that scrapes postcode, housing, and trailing three months' crime data from Streetcheck.co.uk and generates a summary using Amazon Bedrock. Very handy to get a quick understanding of a particular postcode (e.g. if you are considering renting or buying a house in that postcode). Requires boto3 and Markitdown packages.

Uses Amazon Bedrock, hard-coded pricing and model ID's for Claude Sonnet 3.5 v2 and Amazon Nova Pro 1.0
