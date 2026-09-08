import csv
import io

from glue_utils import get_job_arguments, read_source_object, write_output_object, enrich_with_country_code


def transform_csv(content_bytes: bytes) -> bytes:
    text = content_bytes.decode("utf-8")
    reader = csv.DictReader(io.StringIO(text))

    reader.fieldnames = [name.strip() for name in reader.fieldnames]

    output_buffer = io.StringIO()
    writer = csv.DictWriter(output_buffer, fieldnames=["name", "age", "country", "country_code"])
    writer.writeheader()

    for row in reader:
        normalized_row = {key.strip(): (value.strip() if isinstance(value, str) else value) for key, value in row.items()}
        writer.writerow(enrich_with_country_code(normalized_row))

    return output_buffer.getvalue().encode("utf-8")


def main():
    args = get_job_arguments()

    content_bytes = read_source_object(args["SOURCE_BUCKET"], args["SOURCE_KEY"], args["SOURCE_VERSION_ID"])
    transformed_bytes = transform_csv(content_bytes)

    output_key = f"csv/{args['SOURCE_KEY'].split('/')[-1]}"
    write_output_object(args["OUTPUT_BUCKET"], output_key, transformed_bytes)

    print(f"Processed '{args['SOURCE_KEY']}' -> 's3://{args['OUTPUT_BUCKET']}/{output_key}'")


if __name__ == "__main__":
    main()