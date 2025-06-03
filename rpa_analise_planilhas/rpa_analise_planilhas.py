"""
RPA Análise de Planilhas
Segundo RPA do sistema - Analisa planilhas para identificar clientes que precisam de reparcelamento

Desenvolvido em Português Brasileiro
Baseado no PDD seção 7 - Processamento de dados das planilhas
"""

import asyncio
from datetime import datetime, timedelta
from typing import Dict, Any, List
import gspread
from google.oauth2.service_account import Credentials

from core.base_rpa import BaseRPA, ResultadoRPA
from core.notificacoes_simples import notificar_sucesso, notificar_erro

class RPAAnalisePlanilhas(BaseRPA):
    """
    RPA responsável pela análise das planilhas Google Sheets para identificar:
    - Novos contratos para inclusão
    - Pendências de IPTU
    - Contratos que precisam de reajuste (último reajuste há 12 meses)
    - Validação de dados para reparcelamento
    """
    
    def __init__(self):
        super().__init__(nome_rpa="Analise_Planilhas", usar_browser=False)
        self.cliente_sheets = None
    
    async def executar(self, parametros: Dict[str, Any]) -> ResultadoRPA:
        """
        Executa análise completa das planilhas
        
        Args:
            parametros: Deve conter:
                - planilha_calculo_id: ID da planilha BASE DE CÁLCULO REPARCELAMENTO
                - planilha_apoio_id: ID da planilha Base de apoio
                - credenciais_google: Caminho para credenciais (opcional)
        
        Returns:
            ResultadoRPA com lista de contratos para processamento
        """
        try:
            self.log_progresso("Iniciando análise das planilhas para reparcelamento")
            
            # Valida parâmetros obrigatórios
            planilha_calculo_id = parametros.get("planilha_calculo_id")
            planilha_apoio_id = parametros.get("planilha_apoio_id")
            
            if not planilha_calculo_id or not planilha_apoio_id:
                return ResultadoRPA(
                    sucesso=False,
                    mensagem="IDs das planilhas não fornecidos",
                    erro="Parâmetros 'planilha_calculo_id' e 'planilha_apoio_id' são obrigatórios"
                )
            
            # Conecta ao Google Sheets
            await self._conectar_google_sheets(parametros.get("credenciais_google"))
            
            # Processa novos contratos da planilha de apoio
            self.log_progresso("Processando novos contratos da planilha de apoio")
            novos_contratos = await self._processar_novos_contratos(planilha_apoio_id)
            
            # Processa pendências IPTU
            self.log_progresso("Processando pendências de IPTU")
            pendencias_iptu = await self._processar_pendencias_iptu(planilha_apoio_id)
            
            # Atualiza planilha principal com novos dados
            if novos_contratos or pendencias_iptu:
                self.log_progresso("Atualizando planilha principal com novos dados")
                await self._atualizar_planilha_principal(
                    planilha_calculo_id, novos_contratos, pendencias_iptu
                )
            
            # Identifica contratos para reajuste
            self.log_progresso("Identificando contratos que precisam de reajuste")
            contratos_reajuste = await self._identificar_contratos_reajuste(planilha_calculo_id)
            
            # Gera fila para próximos RPAs
            fila_processamento = await self._gerar_fila_processamento(contratos_reajuste)
            
            # Monta resultado final
            resultado_dados = {
                "novos_contratos_processados": len(novos_contratos),
                "pendencias_iptu_atualizadas": len(pendencias_iptu),
                "contratos_para_reajuste": len(contratos_reajuste),
                "fila_processamento": fila_processamento,
                "detalhes_contratos": contratos_reajuste,
                "timestamp_analise": datetime.now().isoformat()
            }
            
            return ResultadoRPA(
                sucesso=True,
                mensagem=f"Análise concluída - {len(contratos_reajuste)} contratos identificados para reparcelamento",
                dados=resultado_dados
            )
            
        except Exception as e:
            self.log_erro("Erro durante análise das planilhas", e)
            return ResultadoRPA(
                sucesso=False,
                mensagem="Falha na análise das planilhas",
                erro=str(e)
            )
    
    async def _conectar_google_sheets(self, caminho_credenciais: str = None):
        """
        Estabelece conexão com Google Sheets
        
        Args:
            caminho_credenciais: Caminho para arquivo de credenciais
        """
        try:
            if not caminho_credenciais:
                caminho_credenciais = "./credentials/google_service_account.json"
            
            self.log_progresso(f"Conectando ao Google Sheets")
            
            credenciais = Credentials.from_service_account_file(
                caminho_credenciais,
                scopes=[
                    "https://www.googleapis.com/auth/spreadsheets",
                    "https://www.googleapis.com/auth/drive",
                ]
            )
            
            self.cliente_sheets = gspread.authorize(credenciais)
            self.log_progresso("✅ Conectado ao Google Sheets com sucesso")
            
        except Exception as e:
            raise Exception(f"Falha na conexão com Google Sheets: {str(e)}")
    
    async def _processar_novos_contratos(self, planilha_apoio_id: str) -> List[Dict[str, Any]]:
        """
        Processa novos contratos da planilha de apoio conforme PDD seção 7.1
        
        Args:
            planilha_apoio_id: ID da planilha de apoio
            
        Returns:
            Lista de novos contratos encontrados
        """
        try:
            self.log_progresso("Acessando aba NOVOS CONTRATOS da planilha de apoio")
            
            # Abre planilha de apoio
            planilha_apoio = self.cliente_sheets.open_by_key(planilha_apoio_id)
            
            # Acessa aba NOVOS CONTRATOS
            aba_novos_contratos = planilha_apoio.worksheet("NOVOS CONTRATOS")
            
            # Lê todos os dados
            dados_novos_contratos = aba_novos_contratos.get_all_records()
            
            # Filtra contratos válidos (linhas não vazias)
            contratos_validos = []
            for linha, contrato in enumerate(dados_novos_contratos, start=2):
                # Verifica se há dados na linha
                if any(str(valor).strip() for valor in contrato.values() if valor):
                    contrato['linha_planilha'] = linha
                    contratos_validos.append(contrato)
            
            self.log_progresso(f"✅ {len(contratos_validos)} novos contratos encontrados")
            
            return contratos_validos
            
        except Exception as e:
            self.log_erro("Erro ao processar novos contratos", e)
            return []
    
    async def _processar_pendencias_iptu(self, planilha_apoio_id: str) -> List[Dict[str, Any]]:
        """
        Processa pendências de IPTU da planilha de apoio conforme PDD seção 7.2
        
        Args:
            planilha_apoio_id: ID da planilha de apoio
            
        Returns:
            Lista de pendências IPTU encontradas
        """
        try:
            self.log_progresso("Acessando aba Consulta IPTU da planilha de apoio")
            
            # Abre planilha de apoio
            planilha_apoio = self.cliente_sheets.open_by_key(planilha_apoio_id)
            
            # Acessa aba Consulta IPTU
            aba_iptu = planilha_apoio.worksheet("Consulta IPTU")
            
            # Lê todos os dados
            dados_iptu = aba_iptu.get_all_records()
            
            # Filtra pendências válidas
            pendencias_validas = []
            for linha, pendencia in enumerate(dados_iptu, start=2):
                # Verifica se há dados na linha
                if any(str(valor).strip() for valor in pendencia.values() if valor):
                    pendencia['linha_planilha'] = linha
                    pendencias_validas.append(pendencia)
            
            self.log_progresso(f"✅ {len(pendencias_validas)} pendências IPTU encontradas")
            
            return pendencias_validas
            
        except Exception as e:
            self.log_erro("Erro ao processar pendências IPTU", e)
            return []
    
    async def _atualizar_planilha_principal(
        self, 
        planilha_calculo_id: str, 
        novos_contratos: List[Dict[str, Any]], 
        pendencias_iptu: List[Dict[str, Any]]
    ):
        """
        Atualiza planilha principal com dados da planilha de apoio
        Conforme PDD seção 7.1 e 7.2
        
        Args:
            planilha_calculo_id: ID da planilha de cálculo principal
            novos_contratos: Lista de novos contratos
            pendencias_iptu: Lista de pendências IPTU
        """
        try:
            # Abre planilha principal
            planilha_principal = self.cliente_sheets.open_by_key(planilha_calculo_id)
            aba_base_calculo = planilha_principal.worksheet("Base de cálculo")
            
            # Adiciona novos contratos se houver
            if novos_contratos:
                self.log_progresso(f"Adicionando {len(novos_contratos)} novos contratos")
                await self._adicionar_novos_contratos(aba_base_calculo, novos_contratos)
            
            # Atualiza pendências IPTU se houver
            if pendencias_iptu:
                self.log_progresso(f"Atualizando {len(pendencias_iptu)} pendências IPTU")
                await self._atualizar_pendencias_iptu(aba_base_calculo, pendencias_iptu)
            
            self.log_progresso("✅ Planilha principal atualizada com sucesso")
            
        except Exception as e:
            raise Exception(f"Erro ao atualizar planilha principal: {str(e)}")
    
    async def _adicionar_novos_contratos(self, aba_base_calculo, novos_contratos: List[Dict[str, Any]]):
        """
        Adiciona novos contratos à aba Base de cálculo
        
        Args:
            aba_base_calculo: Aba Base de cálculo da planilha principal
            novos_contratos: Lista de novos contratos
        """
        try:
            # Encontra próxima linha vazia
            dados_existentes = aba_base_calculo.get_all_values()
            proxima_linha = len(dados_existentes) + 1
            
            # Adiciona cada contrato
            for contrato in novos_contratos:
                # TODO: Cliente deve implementar mapeamento específico das colunas
                # conforme estrutura da planilha Base de cálculo
                
                # Por enquanto, adiciona dados básicos (cliente deve ajustar)
                linha_dados = [
                    contrato.get('numero_titulo', ''),
                    contrato.get('cliente', ''),
                    contrato.get('empreendimento', ''),
                    contrato.get('cnpj_unidade', ''),
                    contrato.get('indexador', ''),
                    datetime.now().strftime('%d/%m/%Y'),  # Data inclusão
                    # ... outras colunas conforme estrutura específica
                ]
                
                # Atualiza linha na planilha
                range_update = f'A{proxima_linha}:{chr(65 + len(linha_dados) - 1)}{proxima_linha}'
                aba_base_calculo.update(range_update, [linha_dados])
                
                proxima_linha += 1
            
            self.log_progresso(f"✅ {len(novos_contratos)} contratos adicionados")
            
        except Exception as e:
            raise Exception(f"Erro ao adicionar novos contratos: {str(e)}")
    
    async def _atualizar_pendencias_iptu(self, aba_base_calculo, pendencias_iptu: List[Dict[str, Any]]):
        """
        Atualiza coluna de pendências IPTU na planilha principal
        
        Args:
            aba_base_calculo: Aba Base de cálculo
            pendencias_iptu: Lista de pendências IPTU
        """
        try:
            # TODO: Cliente deve implementar lógica específica
            # para mapear pendências IPTU com contratos existentes
            # e atualizar coluna "PENDÊNCIAS PMFI"
            
            self.log_progresso("Atualizando pendências IPTU (implementação específica necessária)")
            
        except Exception as e:
            raise Exception(f"Erro ao atualizar pendências IPTU: {str(e)}")
    
    async def _identificar_contratos_reajuste(self, planilha_calculo_id: str) -> List[Dict[str, Any]]:
        """
        Identifica contratos que precisam de reajuste
        Conforme PDD: últimos reajuste há 12 meses
        
        Args:
            planilha_calculo_id: ID da planilha de cálculo
            
        Returns:
            Lista de contratos que precisam de reajuste
        """
        try:
            self.log_progresso("Analisando coluna 'Último reajuste' para identificar contratos")
            
            # Abre planilha principal
            planilha_principal = self.cliente_sheets.open_by_key(planilha_calculo_id)
            aba_base_calculo = planilha_principal.worksheet("Base de cálculo")
            
            # Lê todos os dados
            dados_contratos = aba_base_calculo.get_all_records()
            
            # Data limite (12 meses atrás)
            data_limite = datetime.now() - timedelta(days=365)
            
            contratos_para_reajuste = []
            
            for linha, contrato in enumerate(dados_contratos, start=2):
                try:
                    # Verifica data do último reajuste
                    ultimo_reajuste_str = contrato.get('Último reajuste', '')
                    
                    if ultimo_reajuste_str:
                        # Converte string para data (formato brasileiro dd/mm/yyyy)
                        ultimo_reajuste = datetime.strptime(ultimo_reajuste_str, '%d/%m/%Y')
                        
                        # Se último reajuste foi há mais de 12 meses
                        if ultimo_reajuste <= data_limite:
                            contrato['linha_planilha'] = linha
                            contrato['dias_desde_ultimo_reajuste'] = (datetime.now() - ultimo_reajuste).days
                            contratos_para_reajuste.append(contrato)
                
                except (ValueError, TypeError) as e:
                    # Data inválida, pula contrato
                    continue
            
            self.log_progresso(f"✅ {len(contratos_para_reajuste)} contratos identificados para reajuste")
            
            return contratos_para_reajuste
            
        except Exception as e:
            self.log_erro("Erro ao identificar contratos para reajuste", e)
            return []
    
    async def _gerar_fila_processamento(self, contratos_reajuste: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Gera fila de processamento para os próximos RPAs (Sienge e Sicredi)
        
        Args:
            contratos_reajuste: Lista de contratos que precisam reajuste
            
        Returns:
            Fila de processamento estruturada
        """
        try:
            self.log_progresso("Gerando fila de processamento para RPAs Sienge e Sicredi")
            
            fila_processamento = []
            
            for contrato in contratos_reajuste:
                # Cria item da fila com dados necessários para os próximos RPAs
                item_fila = {
                    "id_fila": f"reajuste_{contrato.get('numero_titulo', '')}_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
                    "numero_titulo": contrato.get('numero_titulo', ''),
                    "cliente": contrato.get('cliente', ''),
                    "empreendimento": contrato.get('empreendimento', ''),
                    "cnpj_unidade": contrato.get('cnpj_unidade', ''),
                    "indexador": contrato.get('indexador', ''),
                    "ultimo_reajuste": contrato.get('Último reajuste', ''),
                    "dias_desde_ultimo_reajuste": contrato.get('dias_desde_ultimo_reajuste', 0),
                    "linha_planilha": contrato.get('linha_planilha', 0),
                    "status_processamento": "pendente",
                    "prioridade": self._calcular_prioridade(contrato),
                    "timestamp_identificacao": datetime.now().isoformat(),
                    "dados_completos": contrato
                }
                
                fila_processamento.append(item_fila)
            
            # Ordena por prioridade (mais urgente primeiro)
            fila_processamento.sort(key=lambda x: x['prioridade'], reverse=True)
            
            # Salva fila no MongoDB para os próximos RPAs
            await self._salvar_fila_mongodb(fila_processamento)
            
            self.log_progresso(f"✅ Fila de processamento gerada com {len(fila_processamento)} itens")
            
            return fila_processamento
            
        except Exception as e:
            self.log_erro("Erro ao gerar fila de processamento", e)
            return []
    
    def _calcular_prioridade(self, contrato: Dict[str, Any]) -> int:
        """
        Calcula prioridade do contrato baseado em regras de negócio
        
        Args:
            contrato: Dados do contrato
            
        Returns:
            Prioridade (maior número = maior prioridade)
        """
        prioridade = 0
        
        # Mais dias sem reajuste = maior prioridade
        dias_sem_reajuste = contrato.get('dias_desde_ultimo_reajuste', 0)
        prioridade += min(dias_sem_reajuste // 30, 12)  # Máximo 12 pontos
        
        # Contratos sem pendências têm prioridade
        if contrato.get('PENDÊNCIAS PMFI', '').upper() == 'OK':
            prioridade += 5
        
        if contrato.get('PENDÊNCIAS SIENGE', '').upper() == 'OK':
            prioridade += 3
        
        if contrato.get('PENDÊNCIAS SIENGE INAD', '').upper() == 'OK':
            prioridade += 3
        
        return prioridade
    
    async def _salvar_fila_mongodb(self, fila_processamento: List[Dict[str, Any]]):
        """
        Salva fila de processamento no MongoDB para os próximos RPAs
        
        Args:
            fila_processamento: Lista de itens da fila
        """
        try:
            if not self.mongo_manager:
                return
            
            collection = self.mongo_manager.get_collection("fila_reparcelamento")
            
            # Remove fila anterior (se existir)
            await collection.delete_many({"status_processamento": "pendente"})
            
            # Insere nova fila
            if fila_processamento:
                await collection.insert_many(fila_processamento)
            
            self.log_progresso(f"✅ Fila salva no MongoDB: {len(fila_processamento)} itens")
            
        except Exception as e:
            self.log_erro("Erro ao salvar fila no MongoDB", e)

# Função auxiliar para uso direto
async def executar_analise_planilhas(
    planilha_calculo_id: str, 
    planilha_apoio_id: str, 
    credenciais_google: str = None
) -> ResultadoRPA:
    """
    Função auxiliar para executar análise de planilhas diretamente
    
    Args:
        planilha_calculo_id: ID da planilha BASE DE CÁLCULO REPARCELAMENTO
        planilha_apoio_id: ID da planilha Base de apoio
        credenciais_google: Caminho para credenciais (opcional)
        
    Returns:
        ResultadoRPA com resultado da análise
    """
    rpa = RPAAnalisePlanilhas()
    
    parametros = {
        "planilha_calculo_id": planilha_calculo_id,
        "planilha_apoio_id": planilha_apoio_id,
        "credenciais_google": credenciais_google
    }
    
    resultado = await rpa.executar_com_monitoramento(parametros)
    
    # Enviar notificação
    try:
        if resultado.sucesso:
            contratos_encontrados = len(resultado.dados.get('fila_processamento', [])) if resultado.dados else 0
            notificar_sucesso(
                nome_rpa="RPA Análise Planilhas",
                tempo_execucao=f"{resultado.tempo_execucao:.1f}s" if resultado.tempo_execucao else "N/A",
                resultados={
                    "contratos_identificados": contratos_encontrados,
                    "planilhas_analisadas": 2,
                    "status": "Análise concluída"
                }
            )
        else:
            notificar_erro(
                nome_rpa="RPA Análise Planilhas",
                erro=resultado.erro or "Erro desconhecido",
                detalhes=resultado.mensagem
            )
    except Exception as e:
        print(f"Aviso: Falha ao enviar notificação: {e}")
    
    return resultado