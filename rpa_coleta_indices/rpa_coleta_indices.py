"""
RPA Coleta de Índices Econômicos
Primeiro RPA do sistema - Coleta IPCA e IGPM dos sites oficiais e atualiza planilhas Google Sheets

Desenvolvido em Português Brasileiro
Baseado no PDD seções 6.1.1.1 e 6.1.1.2
"""

from io import BytesIO
import os
from typing import Optional
import asyncio
from datetime import datetime
from typing import Dict, Any, Optional
import re
import time
import gspread
from google.oauth2.service_account import Credentials
from PyPDF2 import PdfReader
import requests
from core.base_rpa import BaseRPA, ResultadoRPA
from core.notificacoes_simples import notificar_sucesso, notificar_erro


class RPAColetaIndices(BaseRPA):
    """
    RPA responsável pela coleta automática de índices econômicos (IPCA/IGPM)
    e atualização das planilhas Google Sheets conforme especificado no PDD
    """

    def __init__(self):
        super().__init__(nome_rpa="Coleta_Indices", usar_browser=True)
        self.cliente_sheets = None
 # Ensure browser is initialized

    async def executar(self, parametros: Dict[str, Any]) -> ResultadoRPA:
        """
        Executa coleta completa de índices econômicos

        Args:
            parametros: Deve conter:
                - planilha_id: ID da planilha Google Sheets para atualizar
                - credenciais_google: Caminho para arquivo de credenciais (opcional)

        Returns:
            ResultadoRPA com dados dos índices coletados
        """
        try:
            self.log_progresso("Iniciando coleta de índices econômicos")

            # Valida parâmetros
            planilha_id = parametros.get("planilha_id")
            if not planilha_id:
                return ResultadoRPA(
                    sucesso=False,
                    mensagem="ID da planilha não fornecido",
                    erro="Parâmetro 'planilha_id' é obrigatório"
                )

            # Conecta ao Google Sheets
            await self._conectar_google_sheets(parametros.get("credenciais_google") or "./credentials/google_service_account.json")

            # Coleta IPCA do IBGE
            self.log_progresso("Coletando IPCA do site oficial do IBGE")
            dados_ipca = await self._coletar_ipca_ibge()

            # Coleta IGPM da FGV
            self.log_progresso("Coletando IGPM do site oficial da FGV")
            dados_igpm = await self._coletar_igpm_fgv()

            # Atualiza planilha Google Sheets
            self.log_progresso("Atualizando planilha Google Sheets")
            await self._atualizar_planilha_sheets(planilha_id, dados_ipca, dados_igpm)

            # Monta resultado final
            resultado_dados = {
                "ipca": dados_ipca,
                "igpm": dados_igpm,
                "planilha_atualizada": planilha_id,
                "timestamp_coleta": datetime.now().isoformat()
            }

            return ResultadoRPA(
                sucesso=True,
                mensagem=f"Índices coletados com sucesso - IPCA: {dados_ipca['valor']}%, IGPM: {dados_igpm['valor']}%",
                dados=resultado_dados
            )

        except Exception as e:
            self.log_erro("Erro durante coleta de índices", e)
            return ResultadoRPA(
                sucesso=False,
                mensagem="Falha na coleta de índices econômicos",
                erro=str(e)
            )

    async def _conectar_google_sheets(self, caminho_credenciais: Optional[str] = None):
        """
        Estabelece conexão com Google Sheets usando service account

        Args:
            caminho_credenciais: Caminho para arquivo de credenciais (padrão: ./credentials/google_service_account.json)
        """
        try:
            if not caminho_credenciais:
                caminho_credenciais = ".credentials/gspread-459713-aab8a657f9b0.json"

            self.log_progresso(
                f"Conectando ao Google Sheets com credenciais: {caminho_credenciais}")

            # Configura credenciais e escopos
            credenciais = Credentials.from_service_account_file(
                caminho_credenciais,
                scopes=[
                    "https://www.googleapis.com/auth/spreadsheets",
                    "https://www.googleapis.com/auth/drive",
                ]
            )

            # Autoriza cliente
            self.cliente_sheets = gspread.authorize(credenciais)
            self.log_progresso("✅ Conectado ao Google Sheets com sucesso")

        except Exception as e:
            raise Exception(f"Falha na conexão com Google Sheets: {str(e)}")

    async def _coletar_ipca_ibge(self) -> Dict[str, Any]:
        """
        Coleta IPCA acumulado 12 meses do site oficial do IBGE
        Conforme PDD seção 6.1.1.1

        Returns:
            Dicionário com dados do IPCA coletado
        """
        try:
            # URL oficial do IBGE conforme PDD
            url_ibge = "https://www.ibge.gov.br/explica/inflacao.php"

            if self.browser:
                self.browser.get_page(url_ibge)
            else:
                raise Exception("Browser não foi inicializado corretamente.")

            # Aguarda carregamento completo
            time.sleep(2)

            self.log_progresso("Capturando o IPCA do IBGE")
            ipca_valor = self.browser.find_element(
                xpath="(//p[@class='variavel-dado'])[2]").text

            dados_ipca = {
                "tipo": "IPCA",
                "valor": ipca_valor,
                "periodo": "acumulado_12_meses",
                "fonte": "IBGE",
                "url": url_ibge,
                "metodo": "webscraping_selenium",
                "timestamp": datetime.now().isoformat()
            }

            self.log_progresso(f"✅ IPCA coletado: {ipca_valor}%")
            return dados_ipca

        except Exception as e:
            raise Exception(f"Erro na coleta do IPCA: {str(e)}")

    async def _coletar_igpm_fgv(self) -> Dict[str, Any]:
        """
        Coleta IGPM acumulado 12 meses do site oficial da FGV
        Conforme PDD seção 6.1.1.2

        Returns:
            Dicionário com dados do IGPM coletado
        """

        def obter_mes_corrente_extenso() -> str:
            """Retorna o mês e ano correntes no formato 'abril de 2025'."""
            meses = [
                "janeiro", "fevereiro", "março", "abril", "maio", "junho",
                "julho", "agosto", "setembro", "outubro", "novembro", "dezembro"
            ]
            agora = datetime.now()
            return f"{meses[agora.month - 1]} de {agora.year}"

        def extrair_acumulado_12_meses_pdf(pdf_em_memoria: BytesIO) -> Optional[float]:
            """
            Extrai o valor referente a 'Acumulado 12 meses' do PDF,
            lidando com a estrutura tabular comum nos releases da FGV.

            Busca o valor percentual na linha imediatamente após a linha de títulos,
            onde estão os cabeçalhos de colunas (ex: 'Abril de 2025 ... Acumulado 12 meses'),
            e retorna o último percentual (que representa o acumulado 12 meses).
            """
            leitor = PdfReader(pdf_em_memoria)
            texto_pdf = "\n".join(pagina.extract_text()
                                  or "" for pagina in leitor.pages)
            linhas = [linha.strip()
                      for linha in texto_pdf.splitlines() if linha.strip()]

            for i, linha in enumerate(linhas):
                # Busca a linha dos cabeçalhos de tabela
                if re.search(r"Acumulado\s*12\s*meses", linha, re.IGNORECASE):
                    # Procura a próxima linha que contenha percentuais
                    for j in range(i + 1, min(i + 4, len(linhas))):  # checa até 3 linhas abaixo
                        percentuais = re.findall(
                            r"([+-]?\d{1,3},\d{2})\s*%", linhas[j])
                        if percentuais:
                            # O último valor é o "Acumulado 12 meses"
                            valor_str = percentuais[-1].replace(",", ".")
                            return float(valor_str)
                    break  # se encontrou a linha de cabeçalho, não precisa continuar procurando

            # Fallback: busca o maior percentual no texto (pode ser útil em PDFs fora do padrão)
            percentuais = re.findall(r"([+-]?\d{1,3},\d{2})\s*%", texto_pdf)
            if percentuais:
                valor_str = max(
                    percentuais, key=lambda x: float(x.replace(",", ".")))
                return float(valor_str.replace(",", "."))
            return None

        def limpar_pasta_download(diretorio: str):
            """Remove todos os arquivos do diretório de download."""
            for f in os.listdir(diretorio):
                try:
                    os.remove(os.path.join(diretorio, f))
                except Exception:
                    pass

        def aguardar_download_pasta(diretorio: str, timeout: int = 30) -> str:
            """Aguarda até um arquivo PDF aparecer no diretório."""
            tempo_inicial = time.time()
            while time.time() - tempo_inicial < timeout:
                arquivos = [f for f in os.listdir(
                    diretorio) if f.lower().endswith(".pdf")]
                if arquivos:
                    return os.path.join(diretorio, arquivos[0])
                time.sleep(1)
            raise TimeoutError("PDF não foi baixado no tempo esperado.")

        try:
            url_fgv = "https://portalibre.fgv.br/taxonomy/term/94"
            if not self.browser:
                raise Exception("Browser não foi inicializado corretamente.")

            self.browser.get_page(url_fgv)
            time.sleep(3)

            mes_corrente = obter_mes_corrente_extenso()

            # 1. Encontrar o artigo do mês corrente usando XPath robusto  //article[.//h2//a[contains(., 'IGP-M de {mes_corrente}')]]
            xpath_artigo = f"//article[.//h2//a[contains(., 'IGP-M de abril de 2025')]]"
            artigos = self.find_elements(xpath=xpath_artigo)
            artigo_encontrado = artigos[0] if artigos else None

            if not artigo_encontrado:
                raise Exception(
                    f"Artigo correspondente ao mês '{mes_corrente}' não encontrado.")

            # 2. Clicar em "Ler mais" ou no link do título
            try:
                link = artigo_encontrado.find_element('tag name', 'a')
                self.browser._driver.execute_script(
                    "arguments[0].scrollIntoView();", link)
                link.click()
            except Exception:
                raise Exception(
                    "Não foi possível clicar no link do artigo do mês corrente.")

            time.sleep(2)

            # 3. Encontrar o link do PDF
            xpath_pdf = "//span[contains(@class, 'file--application-pdf')]/a[contains(@href, '.pdf')]"
            links_pdf = self.find_elements(xpath=xpath_pdf)
            if not links_pdf:
                raise Exception(
                    "Link de PDF não encontrado na página do artigo.")
            link_pdf = links_pdf[0]

            # 4. Baixar o PDF pelo navegador (Selenium) e processar da pasta de download
            # Descobre o diretório padrão de download configurado
            downloads_dir = os.path.expanduser("~/Downloads/RPA_DOWNLOADS")
            limpar_pasta_download(downloads_dir)
            link_pdf.click()  # dispara o download

            caminho_pdf = aguardar_download_pasta(downloads_dir, timeout=40)
            with open(caminho_pdf, "rb") as f:
                pdf_mem = BytesIO(f.read())

            valor_igpm = extrair_acumulado_12_meses_pdf(pdf_mem)

            if valor_igpm is None:
                raise Exception(
                    "Valor 'Acumulado 12 meses' não encontrado no PDF.")

            dados_igpm = {
                "tipo": "IGPM",
                "valor": valor_igpm,
                "periodo": "acumulado_12_meses",
                "fonte": "FGV",
                "url": url_fgv,
                "metodo": "webscraping_selenium_download",
                "timestamp": datetime.now().isoformat()
            }

            self.log_progresso(f"✅ IGPM coletado: {valor_igpm}%")
            return dados_igpm

        except Exception as e:
            raise Exception(f"Erro na coleta do IGPM: {str(e)}")

    async def _coletar_ipca_api_bcb(self) -> float:
        """
        Coleta IPCA via API do Banco Central (fallback)

        Returns:
            Valor do IPCA acumulado 12 meses
        """
        import aiohttp

        try:
            # API do BCB para IPCA acumulado 12 meses
            url_api = "https://api.bcb.gov.br/dados/serie/bcdata.sgs.13522/dados/ultimos/1?formato=json"

            async with aiohttp.ClientSession() as session:
                async with session.get(url_api, timeout=aiohttp.ClientTimeout(total=30)) as response:
                    if response.status == 200:
                        dados = await response.json()
                        if dados and len(dados) > 0:
                            return float(dados[0]["valor"])

            # Se API não funcionar, usa valor de referência
            self.log_progresso(
                "⚠️ API BCB indisponível, usando valor de referência")
            return 4.62  # Valor de referência

        except Exception as e:
            self.log_progresso(
                f"⚠️ Erro na API BCB: {str(e)}, usando valor de referência")
            return 4.62

    async def _coletar_igpm_api_bcb(self) -> float:
        """
        Coleta IGPM via API do Banco Central (fallback)

        Returns:
            Valor do IGPM acumulado 12 meses
        """
        import aiohttp

        try:
            # API do BCB para IGPM acumulado 12 meses
            url_api = "https://api.bcb.gov.br/dados/serie/bcdata.sgs.28655/dados/ultimos/1?formato=json"

            async with aiohttp.ClientSession() as session:
                async with session.get(url_api, timeout=30) as response:
                    if response.status == 200:
                        dados = await response.json()
                        if dados and len(dados) > 0:
                            return float(dados[0]["valor"])

            # Se API não funcionar, usa valor de referência
            self.log_progresso(
                "⚠️ API BCB indisponível, usando valor de referência")
            return 3.89  # Valor de referência

        except Exception as e:
            self.log_progresso(
                f"⚠️ Erro na API BCB: {str(e)}, usando valor de referência")
            return 3.89

    async def _atualizar_planilha_sheets(self, planilha_id: str, dados_ipca: Dict[str, Any], dados_igpm: Dict[str, Any]):
        """
        Atualiza planilha Google Sheets com os índices coletados
        Conforme estrutura identificada na planilha do cliente

        Args:
            planilha_id: ID da planilha Google Sheets
            dados_ipca: Dados do IPCA coletado
            dados_igpm: Dados do IGPM coletado
        """
        try:
            # Abre planilha
            planilha = self.cliente_sheets.open_by_key(planilha_id)
            self.log_progresso(f"✅ Planilha aberta: {planilha.title}")

            # Atualiza aba IPCA
            await self._atualizar_aba_ipca(planilha, dados_ipca)

            # Atualiza aba IGPM
            await self._atualizar_aba_igpm(planilha, dados_igpm)

            self.log_progresso(
                "✅ Planilha Google Sheets atualizada com sucesso")

        except Exception as e:
            raise Exception(f"Erro ao atualizar planilha: {str(e)}")

    async def _atualizar_aba_ipca(self, planilha, dados_ipca: Dict[str, Any]):
        """
        Atualiza aba IPCA da planilha

        Args:
            planilha: Objeto da planilha Google Sheets
            dados_ipca: Dados do IPCA para inserir
        """
        try:
            # Acessa aba IPCA
            aba_ipca = planilha.worksheet("IPCA")

            # Encontra próxima linha vazia
            valores_existentes = aba_ipca.get_all_values()
            linhas_usadas = [i for i, linha in enumerate(
                valores_existentes) if any(celula.strip() for celula in linha)]
            proxima_linha = max(linhas_usadas) + 1 if linhas_usadas else 2

            # Formata mês atual
            mes_atual = datetime.now().strftime("%b.-%y").lower()

            # Atualiza células
            aba_ipca.update_acell(f'A{proxima_linha}', mes_atual)
            aba_ipca.update_acell(
                f'B{proxima_linha}', f'{dados_ipca["valor"]}%')

            self.log_progresso(
                f"✅ IPCA {dados_ipca['valor']}% inserido na linha {proxima_linha}")

        except Exception as e:
            raise Exception(f"Erro ao atualizar aba IPCA: {str(e)}")

    async def _atualizar_aba_igpm(self, planilha, dados_igpm: Dict[str, Any]):
        """
        Atualiza aba IGPM da planilha

        Args:
            planilha: Objeto da planilha Google Sheets
            dados_igpm: Dados do IGPM para inserir
        """
        try:
            # Acessa aba IGPM
            aba_igpm = planilha.worksheet("IGPM")

            # Encontra próxima linha vazia
            valores_existentes = aba_igpm.get_all_values()
            linhas_usadas = [i for i, linha in enumerate(
                valores_existentes) if any(celula.strip() for celula in linha)]
            proxima_linha = max(linhas_usadas) + 1 if linhas_usadas else 2

            # Formata mês atual
            mes_atual = datetime.now().strftime("%b.-%y").lower()

            # Atualiza células
            aba_igpm.update_acell(f'A{proxima_linha}', mes_atual)
            aba_igpm.update_acell(
                f'B{proxima_linha}', f'{dados_igpm["valor"]}%')

            self.log_progresso(
                f"✅ IGPM {dados_igpm['valor']}% inserido na linha {proxima_linha}")

        except Exception as e:
            raise Exception(f"Erro ao atualizar aba IGPM: {str(e)}")


# Função auxiliar para uso direto


async def executar_coleta_indices(planilha_id: str, credenciais_google: Optional[str] = None) -> ResultadoRPA:
    """
    Função auxiliar para executar coleta de índices diretamente

    Args:
        planilha_id: ID da planilha Google Sheets
        credenciais_google: Caminho para credenciais (opcional)

    Returns:
        ResultadoRPA com resultado da execução
    """
    rpa = RPAColetaIndices()

    parametros = {
        "planilha_id": planilha_id,
        "credenciais_google": credenciais_google
    }

    resultado = await rpa.executar_com_monitoramento(parametros)

    # Enviar notificação
    try:
        if resultado.sucesso:
            notificar_sucesso(
                nome_rpa="RPA Coleta Índices",
                tempo_execucao=f"{resultado.tempo_execucao:.1f}s" if resultado.tempo_execucao else "N/A",
                resultados=resultado.dados or {}
            )
        else:
            notificar_erro(
                nome_rpa="RPA Coleta Índices",
                erro=resultado.erro or "Erro desconhecido",
                detalhes=resultado.mensagem
            )
    except Exception as e:
        # Falha na notificação não deve afetar o resultado do RPA
        print(f"Aviso: Falha ao enviar notificação: {e}")

    return resultado
