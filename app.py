import argparse
from config import validate_config
from graph import build_graph
from dotenv import load_dotenv



def main():

    load_dotenv()
    parser = argparse.ArgumentParser(description="Generate a draft environmental ESG/BRSR report.")
    parser.add_argument("--project-id", required=True, type=int,
                        help="Numeric project_id from public.project_details.")
    args = parser.parse_args()

    validate_config()
    workflow = build_graph()
    result = workflow.invoke({"project_id": args.project_id})

    print("\nEnvironmental report draft generated.")
    print(f"JSON: {result['output_json']}")
    print(f"PDF:  {result['output_pdf']}")
    print("Review all gaps and warnings before relying on the report.")

if __name__ == "__main__":
    main()
