import csv
from Bio import Entrez
from Bio import Medline
import time
import logging
from urllib.error import HTTPError
from tqdm import tqdm
import colorama
from colorama import Fore, Style
from datetime import datetime, timedelta
import backoff
from itertools import zip_longest
import pandas as pd
from fuzzywuzzy import fuzz

# Initialize colorama for cross-platform colored output
colorama.init()


# Set up logging
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


def construct_pubmed_query(search_terms, years_back):
    """Construct a PubMed query with MeSH terms and date range."""
    query = search_terms
    if years_back:
        end_date = datetime.now()
        start_date = end_date - timedelta(days=years_back * 365)
        date_range = f"{start_date.strftime('%Y/%m/%d')}:{end_date.strftime('%Y/%m/%d')}"
        query += f" AND ({date_range}[Date - Publication])"
    return query


def split_query(query, max_length=2000):
    """Split a long query into smaller chunks."""
    terms = query.split(' AND ')
    chunks = []
    current_chunk = []
    current_length = 0

    for term in terms:
        if current_length + len(term) + 5 > max_length:  # 5 for ' AND '
            chunks.append(' AND '.join(current_chunk))
            current_chunk = [term]
            current_length = len(term)
        else:
            current_chunk.append(term)
            current_length += len(term) + 5

    if current_chunk:
        chunks.append(' AND '.join(current_chunk))

    return chunks


@backoff.on_exception(backoff.expo, HTTPError, max_tries=5)
def fetch_pubmed_records(db, retstart, retmax, webenv, query_key):
    """Fetch PubMed records with exponential backoff retry."""
    return Entrez.efetch(db=db, retstart=retstart, retmax=retmax,
                         webenv=webenv, query_key=query_key,
                         rettype="medline", retmode="text")


def search_pubmed(query, email, api_key, max_results=5000, batch_size=100):
    Entrez.email = email
    Entrez.api_key = api_key

    print(f"{Fore.CYAN}Searching PubMed with query: {query}{Style.RESET_ALL}")

    query_chunks = split_query(query)
    all_results = []

    for chunk in query_chunks:
        try:
            handle = Entrez.esearch(db="pubmed", term=chunk, retmax=max_results, usehistory="y")
            record = Entrez.read(handle)
            handle.close()
        except HTTPError as e:
            print(f"{Fore.RED}HTTP Error {e.code} occurred while searching: {e.reason}{Style.RESET_ALL}")
            logger.error(f"HTTP Error {e.code}: {e.reason}")
            logger.debug(f"Query chunk: {chunk}")
            continue

        count = int(record["Count"])
        webenv = record["WebEnv"]
        query_key = record["QueryKey"]
        print(f"{Fore.GREEN}Found {count} results for current chunk{Style.RESET_ALL}")

        with tqdm(total=min(count, max_results), desc="Fetching records", unit="record") as pbar:
            for start in range(0, min(count, max_results), batch_size):
                end = min(count, start + batch_size)
                try:
                    fetch_handle = fetch_pubmed_records("pubmed", start, batch_size, webenv, query_key)
                    records = Medline.parse(fetch_handle)
                    batch_results = list(records)
                    all_results.extend(batch_results)
                    fetch_handle.close()

                    for record in batch_results:
                        title = record.get('TI', 'No title')[:50] + '...' if len(
                            record.get('TI', '')) > 50 else record.get('TI', 'No title')
                        print(f"{Fore.YELLOW}{title}{Style.RESET_ALL}")

                    pbar.update(len(batch_results))
                except Exception as e:
                    print(f"{Fore.RED}An error occurred: {str(e)}{Style.RESET_ALL}")
                    logger.exception("Error while fetching records")
                    continue
                time.sleep(1)  # Be nice to NCBI servers

    print(f"{Fore.GREEN}Total records fetched: {len(all_results)}{Style.RESET_ALL}")
    return all_results


def extract_info(record):
    # Extract DOI
    doi = ''
    if 'LID' in record:
        for lid in record['LID']:
            if '[doi]' in lid:
                doi = lid.split(' ')[0]
                break
    if not doi and 'AID' in record:
        for aid in record['AID']:
            if '[doi]' in aid:
                doi = aid.split(' ')[0]
                break

    # Extract full publication date
    pub_date = record.get('DP', '')

    # Extract article type
    article_type = '; '.join(record.get('PT', []))

    # Extract authors and their affiliations
    authors = record.get('AU', [])
    affiliations = record.get('AD', [])
    authors_with_affiliations = [f"{author} ({aff})" if aff else author
                                 for author, aff in zip_longest(authors, affiliations, fillvalue='')]

    return {
        # Identification
        'pmid': record.get('PMID', ''),
        'doi': doi,
        'title': record.get('TI', ''),

        # Publication Info
        'authors': '; '.join(authors_with_affiliations),
        'journal': record.get('JT', record.get('TA', '')),  # Full journal title, fallback to abbreviation
        'publication_year': pub_date[:4] if pub_date else '',
        'full_publication_date': pub_date,
        'volume': record.get('VI', ''),
        'issue': record.get('IP', ''),
        'pages': record.get('PG', ''),

        # Study Characteristics
        'article_type': article_type,
        'language': '; '.join(record.get('LA', [])),

        # Content
        'abstract': record.get('AB', ''),
        'keywords': '; '.join(record.get('OT', [])),  # Author-provided keywords

        # Additional Info
        'grants': '; '.join(record.get('GR', [])),
        'publication_status': record.get('PST', ''),

        # Links
        'pubmed_link': f"https://pubmed.ncbi.nlm.nih.gov/{record.get('PMID', '')}/",
        'full_text_link': record.get('PMC', '')  # PubMed Central link if available
    }

def save_to_csv(data, filename):
    if not filename.endswith('.csv'):
        filename += '.csv'

    if not data:
        print(f"{Fore.RED}No data to save to CSV.{Style.RESET_ALL}")
        return

    keys = data[0].keys()
    with open(filename, 'w', newline='', encoding='utf-8') as output_file:
        dict_writer = csv.DictWriter(output_file, keys)
        dict_writer.writeheader()
        dict_writer.writerows(data)
    print(f"{Fore.GREEN}Data saved to {filename}{Style.RESET_ALL}")

def get_years_back():
    """Get number of years to look back from user input."""
    while True:
        years_input = input(f"{Fore.CYAN}Enter number of years to look back (e.g., 5 or 10), or press Enter to include all years: {Style.RESET_ALL}")
        if not years_input:
            return None
        try:
            years = int(years_input)
            if years > 0:
                return years
            else:
                print(f"{Fore.RED}Please enter a positive number.{Style.RESET_ALL}")
        except ValueError:
            print(f"{Fore.RED}Invalid input. Please enter a number.{Style.RESET_ALL}")

def main():
    email = "Input Email Here"
    api_key = "Input API key Here"

    print(f"{Fore.CYAN}Welcome to the Enhanced PubMed Systematic Review Scraper{Style.RESET_ALL}")
    query = input(f"{Fore.CYAN}Enter your PubMed search query (you can use MeSH terms and boolean operators): {Style.RESET_ALL}")
    years_back = get_years_back()
    max_results = int(input(f"{Fore.CYAN}Enter the maximum number of results to retrieve: {Style.RESET_ALL}"))
    output_file = input(f"{Fore.CYAN}Enter the output CSV filename (without .csv extension): {Style.RESET_ALL}")

    try:
        final_query = construct_pubmed_query(query, years_back)
        print(f"{Fore.CYAN}Starting PubMed search with query: {final_query}{Style.RESET_ALL}")
        results = search_pubmed(final_query, email, api_key, max_results)

        if results:
            print(f"{Fore.CYAN}Extracting information...{Style.RESET_ALL}")
            extracted_data = [extract_info(record) for record in tqdm(results, desc="Extracting data", unit="record")]

            print(f"{Fore.CYAN}Saving {len(extracted_data)} records to {output_file}.csv...{Style.RESET_ALL}")
            save_to_csv(extracted_data, output_file)

            print(f"{Fore.GREEN}Process completed successfully!{Style.RESET_ALL}")
        else:
            print(f"{Fore.YELLOW}No results were found or retrieved. Please check your query and try again.{Style.RESET_ALL}")
    except Exception as e:
        print(f"{Fore.RED}An unexpected error occurred: {str(e)}{Style.RESET_ALL}")
        logger.exception("Detailed error information:")


def remove_duplicates(data, threshold=90):
    """
    Remove duplicates from the data based on multiple criteria.

    :param data: List of dictionaries containing the scraped data
    :param threshold: Similarity threshold for fuzzy matching (0-100)
    :return: Tuple containing deduplicated data, duplicate data, and duplicate count
    """
    df = pd.DataFrame(data)

    # Convert to lowercase for better matching
    df['title_lower'] = df['title'].str.lower()
    df['abstract_lower'] = df['abstract'].str.lower()

    duplicates = set()
    duplicate_pairs = []
    for i, row in df.iterrows():
        if i in duplicates:
            continue

        # Check for exact matches on PMID or DOI
        exact_matches = df[(df['pmid'] == row['pmid']) | (df['doi'] == row['doi'])]
        for match_index in exact_matches.index[1:]:
            duplicates.add(match_index)
            duplicate_pairs.append((i, match_index, 'Exact match (PMID/DOI)'))

        # Fuzzy matching on title and abstract
        potential_matches = df[
            (df.index != i) &
            (df['publication_year'] == row['publication_year']) &
            (~df.index.isin(duplicates))
            ]

        for j, match_row in potential_matches.iterrows():
            title_similarity = fuzz.token_sort_ratio(row['title_lower'], match_row['title_lower'])
            abstract_similarity = fuzz.token_sort_ratio(row['abstract_lower'], match_row['abstract_lower'])

            if title_similarity > threshold and abstract_similarity > threshold:
                duplicates.add(j)
                duplicate_pairs.append(
                    (i, j, f'Fuzzy match (Title: {title_similarity}%, Abstract: {abstract_similarity}%)'))

    deduplicated_data = df[~df.index.isin(duplicates)].drop(columns=['title_lower', 'abstract_lower']).to_dict(
        'records')
    duplicate_data = df[df.index.isin(duplicates)].drop(columns=['title_lower', 'abstract_lower']).to_dict('records')

    return deduplicated_data, duplicate_data, duplicate_pairs, len(duplicates)


def save_duplicate_info(duplicate_data, duplicate_pairs, filename):
    """
    Save information about removed duplicates to a CSV file.

    :param duplicate_data: List of dictionaries containing duplicate records
    :param duplicate_pairs: List of tuples containing (original_index, duplicate_index, reason)
    :param filename: Name of the output file
    """
    if not filename.endswith('.csv'):
        filename += '.csv'

    df_duplicates = pd.DataFrame(duplicate_data)
    df_duplicates['duplicate_of'] = ''
    df_duplicates['reason'] = ''

    for original, duplicate, reason in duplicate_pairs:
        df_duplicates.loc[duplicate, 'duplicate_of'] = original
        df_duplicates.loc[duplicate, 'reason'] = reason

    df_duplicates.to_csv(filename, index=False)
    print(f"{Fore.GREEN}Duplicate information saved to {filename}{Style.RESET_ALL}")


def generate_summary(total_records, duplicate_count, final_count, output_file):
    summary = f"""
PubMed Scraping and Deduplication Summary
=========================================
Total records collected: {total_records}
Duplicate records removed: {duplicate_count}
Final unique records: {final_count}

Original data saved to: {output_file}.csv
Deduplicated data saved to: {output_file}_deduplicated.csv
Removed duplicates saved to: {output_file}_duplicates.csv
This summary saved to: {output_file}_summary.txt
"""
    with open(f"{output_file}_summary.txt", 'w') as f:
        f.write(summary)
    print(f"{Fore.GREEN}Summary saved to {output_file}_summary.txt{Style.RESET_ALL}")
    print(summary)


def main():
    email = "kinleydhinata@gmail.com"
    api_key = "fe9b7fa4c14fbc6c61e813bd7863939b2f08"

    print(f"{Fore.CYAN}Welcome to the Enhanced PubMed Systematic Review Scraper{Style.RESET_ALL}")
    query = input(
        f"{Fore.CYAN}Enter your PubMed search query (you can use MeSH terms and boolean operators): {Style.RESET_ALL}")
    years_back = get_years_back()
    max_results = int(input(f"{Fore.CYAN}Enter the maximum number of results to retrieve: {Style.RESET_ALL}"))
    output_file = input(f"{Fore.CYAN}Enter the output CSV filename (without .csv extension): {Style.RESET_ALL}")

    try:
        final_query = construct_pubmed_query(query, years_back)
        print(f"{Fore.CYAN}Starting PubMed search with query: {final_query}{Style.RESET_ALL}")
        results = search_pubmed(final_query, email, api_key, max_results)

        if results:
            print(f"{Fore.CYAN}Extracting information...{Style.RESET_ALL}")
            extracted_data = [extract_info(record) for record in tqdm(results, desc="Extracting data", unit="record")]

            print(f"{Fore.CYAN}Saving {len(extracted_data)} records to {output_file}.csv...{Style.RESET_ALL}")
            save_to_csv(extracted_data, output_file)

            print(f"{Fore.CYAN}Removing duplicates...{Style.RESET_ALL}")
            deduplicated_data, duplicate_data, duplicate_pairs, duplicate_count = remove_duplicates(extracted_data)

            print(
                f"{Fore.CYAN}Saving {len(deduplicated_data)} deduplicated records to {output_file}_deduplicated.csv...{Style.RESET_ALL}")
            save_to_csv(deduplicated_data, f"{output_file}_deduplicated")

            print(
                f"{Fore.CYAN}Saving {duplicate_count} removed duplicates to {output_file}_duplicates.csv...{Style.RESET_ALL}")
            save_duplicate_info(duplicate_data, duplicate_pairs, f"{output_file}_duplicates")

            generate_summary(len(extracted_data), duplicate_count, len(deduplicated_data), output_file)

            print(f"{Fore.GREEN}Process completed successfully!{Style.RESET_ALL}")
        else:
            print(
                f"{Fore.YELLOW}No results were found or retrieved. Please check your query and try again.{Style.RESET_ALL}")
    except Exception as e:
        print(f"{Fore.RED}An unexpected error occurred: {str(e)}{Style.RESET_ALL}")
        logger.exception("Detailed error information:")


if __name__ == "__main__":
    main()