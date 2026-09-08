import json

from glue_utils import get_job_arguments, read_source_object, write_output_object, enrich_with_country_code


def transform_json(content_bytes: bytes) -> bytes:
    records = json.loads(content_bytes.decode("utf-8"))
    enriched_records = [enrich_with_country_code(dict(record)) for record in records]
    return json.dumps(enriched_records, indent=2).encode("utf-8")


def main():
    args = get_job_arguments()

    content_bytes = read_source_object(args["SOURCE_BUCKET"], args["SOURCE_KEY"], args["SOURCE_VERSION_ID"])
    transformed_bytes = transform_json(content_bytes)

    output_key = f"json/{args['SOURCE_KEY'].split('/')[-1]}"
    write_output_object(args["OUTPUT_BUCKET"], output_key, transformed_bytes)

    print(f"Processed '{args['SOURCE_KEY']}' -> 's3://{args['OUTPUT_BUCKET']}/{output_key}'")


if __name__ == "__main__":
    main()
