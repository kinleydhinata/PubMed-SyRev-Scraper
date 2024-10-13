# PubMed Systematic Review Scraper

This repository contains a Python-based scraper for systematically retrieving and processing research articles from PubMed. The tool is designed to assist researchers in conducting systematic reviews by automating the process of querying PubMed, extracting metadata, and saving the results in a structured format. Additionally, the tool includes functions to handle duplicate entries and generate comprehensive summaries.

## Features

- **Automated PubMed Queries**: Search PubMed using custom queries including MeSH terms and Boolean operators.
- **Query Chunk Splitting**: Automatically splits lengthy queries into smaller, manageable chunks to stay within PubMed's query limits.
- **Retry Mechanism**: Implements an exponential backoff strategy to handle HTTP errors gracefully when fetching records.
- **Metadata Extraction**: Extracts key metadata such as title, DOI, publication date, author affiliations, and abstracts.
- **Duplicate Removal**: Uses exact and fuzzy matching techniques to identify and remove duplicate records, ensuring a clean dataset.
- **CSV Export**: Saves extracted data in CSV format, with separate files for the complete dataset, deduplicated records, and removed duplicates.
- **Summary Generation**: Generates a summary report for each systematic review, detailing the number of records retrieved and deduplicated.

## Installation

To run this scraper, ensure you have Python 3.7 or higher installed. Install the required dependencies using pip:

```sh
pip install -r requirements.txt
```

The following dependencies are required:
- [Biopython](https://biopython.org/)
- [tqdm](https://tqdm.github.io/)
- [colorama](https://pypi.org/project/colorama/)
- [fuzzywuzzy](https://github.com/seatgeek/fuzzywuzzy)
- [backoff](https://pypi.org/project/backoff/)

## Usage

1. **Prepare API Key**: Obtain an API key from NCBI to ensure compliance with rate limits. You will need to provide your email and API key when prompted.
2. **Run the Script**: Execute the script to start querying PubMed and retrieve data.

```sh
python PubMed-SyRev-Scraper.py
```

3. **Input Parameters**: You will be prompted to provide the following:
   - PubMed search query (using MeSH terms and Boolean operators).
   - Number of years to look back for publications.
   - Maximum number of records to retrieve.
   - Output CSV filename (without extension).

4. **Review Results**: Once completed, the results will be saved in CSV files. Deduplicated records and duplicates will be stored separately.

## Example

Here's a quick example of how to use the script:

```plaintext
Welcome to the Enhanced PubMed Systematic Review Scraper
Enter your PubMed search query (you can use MeSH terms and boolean operators): "cancer AND immunotherapy"
Enter number of years to look back (e.g., 5 or 10), or press Enter to include all years: 5
Enter the maximum number of results to retrieve: 500
Enter the output CSV filename (without .csv extension): cancer_immunotherapy
```

This will create CSV files containing metadata for relevant publications on cancer and immunotherapy from the last 5 years.

## Key Functions

- **`construct_pubmed_query()`**: Builds PubMed queries with date ranges.
- **`split_query()`**: Splits long queries to stay within PubMed limits.
- **`search_pubmed()`**: Conducts the search using the NCBI Entrez API, fetching the results in batches.
- **`extract_info()`**: Extracts useful metadata from PubMed records.
- **`remove_duplicates()`**: Removes duplicates based on exact and fuzzy matching.
- **`save_to_csv()`**: Saves data to CSV files.
- **`generate_summary()`**: Generates a summary report for the systematic review.

## Notes

- Be mindful of the rate limits when making repeated requests to PubMed. The script includes a retry mechanism and delay to avoid overwhelming the NCBI servers.
- Ensure your search query is well-formulated with proper MeSH terms for more accurate results.
- The script includes fuzzy matching (using `fuzzywuzzy`) to identify potential duplicate records based on similarities in title and abstract.

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Contributing

Contributions are welcome! Feel free to open issues or submit pull requests to enhance the functionality of this tool.

## Acknowledgements

- Thanks to the developers of [Biopython](https://biopython.org/) for providing tools to interface with PubMed.
- This project makes use of several Python libraries, including `colorama` for colored terminal output and `tqdm` for progress bars, to enhance user experience.

## Contact

For questions or suggestions, please contact [Your Name] at [Your Email].

