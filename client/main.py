from .llm_agent import run_agent

def main():
    command = input("명령어 입력 >> ")
    run_agent(command)

if __name__ == "__main__":
    main()
