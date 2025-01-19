import requests
import time
import random
import tempfile
import os
from markitdown import MarkItDown
import boto3
import sys
import warnings
import re
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta  # You might need to pip install python-dateutil

#MODEL_ID = "anthropic.claude-3-5-sonnet-20241022-v2:0"
MODEL_ID = "amazon.nova-lite-v1:0"
AWS_REGION = "us-east-1"
AWS_PROFILE = "us-east-1-profile"

# Suppress the specific datetime warning from botocore
warnings.filterwarnings('ignore', category=DeprecationWarning,
                       message='datetime.datetime.utcnow.*')

def cleanup_temp_file(filename):
    try:
        os.unlink(filename)
    except OSError as e:
        print(f"Warning: Could not delete temporary file {filename}: {e}")
    finally:
        if os.path.exists(filename):
            print(f"Warning: Temporary file {filename} still exists")

def get_streetcheck_data(postcode, data_type="postcode", data_date=None):
    """
    Get data from StreetCheck for a given postcode
    Args:
        postcode: UK postcode
        data_type: Either "postcode" or "houseprices" for different page types
    Returns:
        str: HTML content of the page
    """
    # Clean the postcode - remove spaces and convert to uppercase
    postcode = postcode.strip().replace(" ", "").lower()

    # Base URL with path based on data type
    base_url = "https://www.streetcheck.co.uk/"
    if data_type == "houseprices":
        base_url += "houseprices/"
    elif data_type == "postcode":
        base_url += "postcode/"
    elif data_type == "crime":
        base_url += f"crime/"
    else:
        raise ValueError("data_type must be either 'postcode', 'houseprices', or 'crime'")

    # Common user agents to rotate between
    user_agents = [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:122.0) Gecko/20100101 Firefox/122.0"
    ]

    # Headers to simulate a real browser
    headers = {
        "User-Agent": random.choice(user_agents),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.5",
        "Accept-Encoding": "gzip, deflate, br",
        "DNT": "1",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "none",
        "Sec-Fetch-User": "?1"
    }

    try:
        # Add a small random delay to simulate human behavior
        time.sleep(random.uniform(1, 3))

        # Make the request
        response = requests.get(
            base_url + postcode + (f"/{data_date}" if data_date else ""),
            headers=headers,
            timeout=10,
            verify=True
        )

        # Raise an exception for bad status codes
        response.raise_for_status()
        print(f"Fetched {data_type} data for postcode {postcode}" + (f"/{data_date}" if data_date else ""))

        # Return the HTML content
        return response.text

    except requests.RequestException as e:
        print(f"Error fetching {data_type} data for postcode {postcode}: {str(e)}")
        return None




def initialize_bedrock_client(aws_profile: str) -> boto3.client:
    session = boto3.Session(profile_name=aws_profile)
    return session.client('bedrock-runtime', AWS_REGION)


def get_content_summary(bedrock_runtime: boto3.client, text_content: str) -> str:
    prompt = '''
You are a data analyst specializing in demographic and housing statistics. Your task is to create a concise, factual summary of a given area based on the provided information. Here's the content you need to analyze:

<area_description>
{text}
</area_description>

Please follow these steps to create your summary:

1. Carefully read through the provided content.

2. In your analysis, identify and extract key information about:
    - The area's general characteristics
    - Available amenities, including broadband speed
    - Demographics
    - Crime (note that three months worth of crime data is here, break down by month); make sure to report the total count by month
    - Notable statistics

3. Pay special attention to the following categories and their associated percentages:
    - Housing types
    - Housing tenure
    - Housing prices
    - Household deprivation
    - Economic activity
    - Ethnic groups

4. Specifically highlight:
    - The percentage of social rented housing
    - The percentage of households with deprivation across all dimensions
    - The level of unemployment
    - The total count of crimes reported by category

5. Present your work as a crisp summary of all the data you have gathered. Make sure to:
    - Quote specific statistics and percentages from the text for each category
    - Calculate the total percentage for each category
    - If percentages within a category exceed 100%, show your work in adjusting the figures proportionally to ensure they sum to 100%
    - Organize the extracted information into clear categories (e.g., Housing, Demographics, Economy)
    - List any other key facts and statistics you've identified; make sure to note the level of deprivation in total, and in more than one dimension

Remember to maintain a professional and objective tone throughout your data extraction and summary.

Here is an example of the report that you must write:

<example_report>
### Summary of Cockfosters Road, Barnet, EN4 0JT

#### General Characteristics

Cockfosters Road in Barnet, London, is an urban area under the Enfield Local Authority. It falls within the Cockfosters ward/electoral division and the Southgate and Wood Green constituency. The postcode EN4 0JT is part of this area.


#### Amenities

- **Broadband:** The postcode supports superfast broadband (30Mbps+).
- **Nearby Services:** The area has several nearby railway stations, Tube/DLR stations, primary and secondary schools, GP practices, dentists, hospitals, and opticians.


#### Demographics

- **Population:** 498 residents.
- **Gender:** 45% male, 55% female.
- **Age Groups:** A significant proportion (41%) are aged 65+.
- **Health:** 81.7% rated their health as Very Good or Good.

- **Education:** 187 residents have a degree or similar professional qualification, 11 have an apprenticeship, 44 have HNC, HND, or 2+ A Levels, 48 have 5+ GCSEs, 36 have 1-4 GCSEs, and 98 have no qualifications.

- **Ethnic Groups:** 71% White, 17 Mixed Ethnicity, 46 Indian, 3 Pakistani, 5 Chinese, 13 Other Asian, 5 Black African, 5 Black Caribbean, 3 Other Black/African/Caribbean, 1 Arab, 47 Other.

- **Country of Birth:** 375 born in the UK, 47 from the European Union, 18 from Rest of Europe, 23 from Africa, 32 from Middle East and Asia, 4 from The Americas.

- **Religion:** 87 No Religion, 223 Christian, 6 Buddhist, 28 Hindu, 77 Jewish, 20 Muslim, 3 Sikh, 13 Other Religion, 44 Not Stated.


#### Economy

- **Economic Activity:** 109 Full-Time Employee, 41 Part-Time Employee, 24 Self Employed (No Subordinates), 22 Self Employed (With Subordinates), 14 Unemployed, 15 Full-Time Student, 178 Retired, 20 Looking After Home or Family, 6 Long-Term Sick or Disabled, 12 Other.


#### Housing

- **Housing Types:** 85 Detached, 7 Semi-Detached, 24 Terraced, 86 Flat (Purpose-Built), 6 Flat (Converted), Total 208.

- **Housing Tenure:** 114 Owned Outright, 54 Owned with Mortgage, 1 Rented: Other Social, 30 Rented: Private Landlord inc. letting agents, 8 Rented: Other, Total 207.

- **Household Deprivation:** 125 Not Deprived, 70 Deprived In One Dimension, 13 Deprived In Two Dimensions, 1 Deprived In Three Dimensions, Total 209.


#### Crime Statistics

- **September 2024:** 3 Anti-social behaviour, 1 Criminal damage and arson, 1 Drugs, 4 Other theft, 2 Robbery, 4 Shoplifting, 1 Vehicle crime, 6 Violence and sexual offences, 1 Other crime.

- **October 2024:** 1 Anti-social behaviour, 1 Vehicle crime.

- **November 2024:** 1 Anti-social behaviour, 1 Public order, 1 Vehicle crime, 1 Violence and sexual offences.


#### Notable Statistics

- **Social Rented Housing:** 0.5% (1/207).
- **Households with Deprivation Across All Dimensions:** 0.5% (1/209).
- **Unemployment:** 3.2% (14/441).
- **Total Crimes Reported:**
    - **September 2024:** 23 crimes.
    - **October 2024:** 2 crimes.
    - **November 2024:** 4 crimes.
</example_report>

    '''.format(text=text_content)

    messages = [
        {
            "role": "user",
            "content": [
                {
                    "text": prompt
                }
            ]
        }
    ]

    inference_config = {
        "temperature": 0.0,
        "maxTokens": 2048,
        "topP": 1,
    }

    try:
        response = bedrock_runtime.converse(
            modelId=MODEL_ID,
            messages=messages,
            inferenceConfig=inference_config
        )
        return response['output']['message']['content'][0]['text']
    except Exception as err:
        print(f"Error getting summary: {err.response['Error']['Message']}")
        return None


# get trailing 3 months of crime data
def get_three_months_data(postcode):
    results = ""
    current_date = datetime.now()
    four_months_ago = current_date - relativedelta(months=4)

    # Iterate through the last 3 months (2 months ago, 1 month ago, and current month)
    for i in range(3):
        # Calculate the date for this iteration
        target_date = four_months_ago + relativedelta(months=i)
        formatted_date = target_date.strftime('%Y/%m')

        # Get data for this month
        postcode_html = get_streetcheck_data(postcode, "crime", formatted_date)

        if postcode_html:
            with tempfile.NamedTemporaryFile(mode='w', suffix='.html', delete=False) as temp_file:
                temp_file.write(postcode_html)
                md = MarkItDown()
                result = md.convert(temp_file.name)
                # Add month identifier before the content
                results += f"Data for {formatted_date}:\n"
                results += result.text_content + "\n\n"  # Add double newline for separation
                cleanup_temp_file(temp_file.name)

    return results

# Modified main function to include the summarization
def main():
    # Set default postcode for Knightsbridge/Kensington area
    default_postcode = "SW72BU"  # One of London's most expensive areas

    # Get postcode from command line or use default
    if len(sys.argv) > 1:
        postcode = sys.argv[1].strip().replace(" ", "").lower()
        if not postcode:  # If postcode is empty after cleaning
            print(f"Invalid postcode provided, using default: {default_postcode} (Knightsbridge)")
            postcode = default_postcode
    else:
        print(f"No postcode provided, using default: {default_postcode} (Knightsbridge)")
        postcode = default_postcode

    # Get both types of HTML content
    postcode_html = get_streetcheck_data(postcode, "postcode")
    prices_html = get_streetcheck_data(postcode, "houseprices")

    results = ""
    # Process postcode data if available
    if postcode_html:
        with tempfile.NamedTemporaryFile(mode='w', suffix='.html', delete=False) as temp_file:
            temp_file.write(postcode_html)
            md = MarkItDown()
            result = md.convert(temp_file.name)
            results += result.text_content + "\n\n"  # Add double newline for separation
            cleanup_temp_file(temp_file.name)

    if prices_html:
        with tempfile.NamedTemporaryFile(mode='w', suffix='.html', delete=False) as temp_file:
            temp_file.write(prices_html)
            md = MarkItDown()
            result = md.convert(temp_file.name)
            results += result.text_content
            cleanup_temp_file(temp_file.name)

    # get the crime data
    crime_text = get_three_months_data(postcode)
    results += crime_text

    # Initialize Bedrock client
    bedrock_runtime = initialize_bedrock_client(AWS_PROFILE)

    # Get summary
    summary = get_content_summary(bedrock_runtime, results)
    print(f"\n\nSummary for {postcode}:\n{summary}\n")

    input_tokens = len(results) // 4
    output_tokens = len(summary) // 4

    # price for Claude Sonnet 3.5 v2 is 0.003 and 0.015
    # for Nova Pro 1.0 it is 0.0008 and 0.0032
    input_price = input_tokens // 1000 * 0.0008
    output_price = output_tokens // 1000 * 0.0032

    print(f"\nToken Estimation:")
    print(f"Input tokens (approx): {input_tokens:,} (${input_price:.2f})")
    print(f"Output tokens (approx): {output_tokens:,}  (${output_price:.2f})")
    print(f"Total inference cost: ${(input_price + output_price):.2f}")

if __name__ == "__main__":
    main()
