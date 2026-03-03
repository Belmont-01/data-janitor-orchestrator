import os
from dotenv import load_dotenv, find_dotenv
from errors import PipelineError, FileIngestionError, APIError, InvalidOutputError, AgentTimeoutError

load_dotenv(find_dotenv())

# Fix working directory so relative paths always work
os.chdir(os.path.dirname(os.path.abspath(__file__)))

from orchestrator.boss import run_pipeline

if __name__ == "__main__":
    INPUT_FILE = r"D:\TODAY\PROJECT X\data\raw\sample_messy.csv"
    OUTPUT_DIR = "data/clean"

    print("=" * 50)
    print("  DATA JANITOR & ORCHESTRATOR — Starting Up")
    print("=" * 50)

    try:
        run_pipeline(INPUT_FILE, OUTPUT_DIR)

    except FileIngestionError as e:
        print(f"\n❌ FILE ERROR\n{e}")

    except APIError as e:
        print(f"\n❌ API ERROR\n{e}")
        print("→ Check your GOOGLE_API_KEY in .env")
        print("→ Check your quota at: https://console.cloud.google.com")

    except InvalidOutputError as e:
        print(f"\n❌ OUTPUT ERROR\n{e}")
        print("→ The LLM returned something unexpected. Check data/clean/ for the raw output.")

    except AgentTimeoutError as e:
        print(f"\n❌ TIMEOUT ERROR\n{e}")
        print("→ Try a smaller input file or raise max_rpm in agents/llm_config.py")

    except PipelineError as e:
        print(f"\n❌ PIPELINE ERROR\n{e}")

    except Exception as e:
        print(f"\n❌ UNEXPECTED ERROR: {e}")
        print("→ This is likely a bug. Check the traceback above.")
        raise
