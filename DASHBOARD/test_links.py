
import pandas as pd
import sys

def inspect_spreadsheet(file_path):
    """
    Inspeciona a primeira aba de um arquivo Excel e suas colunas,
    ajudando a diagnosticar problemas de carregamento de dados.
    """
    try:
        # Usa ExcelFile para inspecionar sem carregar todos os dados de uma vez
        xls = pd.ExcelFile(file_path)
    except FileNotFoundError:
        print(f"❌ ERRO: O arquivo '{file_path}' não foi encontrado no diretório.")
        print("Verifique se o nome do arquivo está correto e se ele está na mesma pasta do dashboard.")
        sys.exit(1)
    except Exception as e:
        print(f"❌ ERRO: Ocorreu um erro inesperado ao tentar abrir o arquivo: {e}")
        sys.exit(1)

    sheet_names = xls.sheet_names
    print("="*60)
    print("🔎 INSPECIONANDO A PLANILHA 'base_de_dados_IGs.xlsx'")
    print("="*60)
    print(f"\n📋 Abas (worksheets) encontradas no arquivo:")
    for name in sheet_names:
        print(f"- '{name}'")

    print("\n" + "-"*25)

    # Verifica se existe alguma aba
    if not sheet_names:
        print(f"\n❌ ERRO CRÍTICO: Nenhuma aba (worksheet) foi encontrada no arquivo!")
        print("="*60)
        sys.exit(1)
    
    first_sheet = sheet_names[0]
    print(f"\n✅ SUCESSO: Inspecionando a primeira aba encontrada: '{first_sheet}'.")
    if len(sheet_names) > 1:
        print(f"   (O dashboard sempre lerá a primeira aba, ignorando as outras: {sheet_names[1:]})")
    
    try:
        # Agora lê a primeira aba e verifica as colunas
        df = pd.read_excel(file_path, sheet_name=0)
        print(f"\n🏛️ Nomes das colunas na aba '{first_sheet}':")
        for col_name in df.columns:
            print(f"- '{col_name}'")
        
        print("\n" + "-"*25)
        print("\n✅ SUCESSO: A estrutura da planilha parece correta para o dashboard.")
        print("Se o erro persistir, verifique se os nomes das colunas acima correspondem\n"
              "exatamente aos esperados pelo código (sem espaços extras ou acentos diferentes).")

    except Exception as e:
        print(f"\n❌ ERRO: A aba '{first_sheet}' foi encontrada, mas ocorreu um erro ao ler seus dados: {e}")

    print("="*60)

if __name__ == "__main__":
    FILE_PATH = "base_de_dados_IGs.xlsx"
    inspect_spreadsheet(FILE_PATH)
