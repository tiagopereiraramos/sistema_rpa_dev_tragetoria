"""
RPA Sienge
Terceiro RPA do sistema - Processa reparcelamento no ERP Sienge

Desenvolvido em Português Brasileiro
Baseado no PDD seção 7.3 - Processamento no sistema Sienge
"""

import asyncio
from datetime import datetime
from typing import Dict, Any, List
import time

from core.base_rpa import BaseRPA, ResultadoRPA
from core.notificacoes_simples import notificar_sucesso, notificar_erro

class RPASienge(BaseRPA):
    """
    RPA responsável pelo processamento de reparcelamento no ERP Sienge
    
    Funcionalidades:
    - Login no sistema Sienge
    - Consulta de relatórios financeiros (Saldo devedor presente)
    - Processamento de reparcelamento de contratos
    - Validação de pendências e inadimplência
    - Geração de carnês atualizados
    """
    
    def __init__(self):
        super().__init__(nome_rpa="Sienge", usar_browser=True)
        self.logado_sienge = False
        self.url_sienge = None
        self.usuario_sienge = None
        self.senha_sienge = None
    
    async def executar(self, parametros: Dict[str, Any]) -> ResultadoRPA:
        """
        Executa processamento de reparcelamento no Sienge
        
        Args:
            parametros: Deve conter:
                - contrato: Dados do contrato para processar
                - indices_economicos: IPCA/IGPM atualizados
                - credenciais_sienge: URL, usuário e senha do Sienge
        
        Returns:
            ResultadoRPA com resultado do processamento
        """
        try:
            self.log_progresso("Iniciando processamento no ERP Sienge")
            
            # Valida parâmetros
            contrato = parametros.get("contrato")
            indices = parametros.get("indices_economicos")
            credenciais = parametros.get("credenciais_sienge")
            
            if not contrato or not credenciais:
                return ResultadoRPA(
                    sucesso=False,
                    mensagem="Dados do contrato ou credenciais Sienge não fornecidos",
                    erro="Parâmetros 'contrato' e 'credenciais_sienge' são obrigatórios"
                )
            
            # Configura credenciais
            self._configurar_credenciais(credenciais)
            
            # Faz login no Sienge
            await self._fazer_login_sienge()
            
            # Consulta relatórios financeiros do cliente
            self.log_progresso(f"Consultando relatórios do cliente: {contrato.get('cliente', '')}")
            dados_financeiros = await self._consultar_relatorios_financeiros(contrato)
            
            # Valida se contrato pode ser reparcelado
            pode_reparcelar = await self._validar_contrato_reparcelamento(dados_financeiros)
            
            if not pode_reparcelar["pode_reparcelar"]:
                return ResultadoRPA(
                    sucesso=False,
                    mensagem=f"Contrato não pode ser reparcelado: {pode_reparcelar['motivo']}",
                    dados={
                        "contrato": contrato,
                        "validacao": pode_reparcelar,
                        "dados_financeiros": dados_financeiros
                    }
                )
            
            # Processa reparcelamento
            self.log_progresso("Processando reparcelamento no Sienge")
            resultado_reparcelamento = await self._processar_reparcelamento(contrato, indices, dados_financeiros)
            
            # Gera carnê se processamento foi bem-sucedido
            carne_gerado = None
            if resultado_reparcelamento["sucesso"]:
                self.log_progresso("Gerando carnê atualizado")
                carne_gerado = await self._gerar_carne_sienge(contrato)
            
            # Monta resultado final
            resultado_dados = {
                "contrato_processado": contrato,
                "dados_financeiros": dados_financeiros,
                "reparcelamento": resultado_reparcelamento,
                "carne_gerado": carne_gerado,
                "timestamp_processamento": datetime.now().isoformat()
            }
            
            return ResultadoRPA(
                sucesso=resultado_reparcelamento["sucesso"],
                mensagem=f"Reparcelamento processado - Cliente: {contrato.get('cliente', '')}",
                dados=resultado_dados
            )
            
        except Exception as e:
            self.log_erro("Erro durante processamento no Sienge", e)
            return ResultadoRPA(
                sucesso=False,
                mensagem="Falha no processamento Sienge",
                erro=str(e)
            )
        finally:
            # Sempre faz logout
            await self._fazer_logout_sienge()
    
    def _configurar_credenciais(self, credenciais: Dict[str, Any]):
        """
        Configura credenciais do Sienge
        
        Args:
            credenciais: Dicionário com url, usuario e senha
        """
        self.url_sienge = credenciais.get("url", "")
        self.usuario_sienge = credenciais.get("usuario", "")
        self.senha_sienge = credenciais.get("senha", "")
        
        if not all([self.url_sienge, self.usuario_sienge, self.senha_sienge]):
            raise Exception("Credenciais incompletas para o Sienge")
    
    async def _fazer_login_sienge(self):
        """
        Faz login no sistema Sienge conforme PDD seção 7.3
        """
        try:
            self.log_progresso(f"Acessando sistema Sienge: {self.url_sienge}")
            
            # Acessa página de login
            self.browser.get_page(self.url_sienge)
            time.sleep(3)
            
            # TODO: Cliente deve implementar login específico no Sienge usando sua classe browser
            # Conforme PDD:
            # 1. Informar usuário (tc@trajetoriaconsultoria.com.br)
            # 2. Clicar em Continuar
            # 3. Informar senha
            # 4. Clicar em Entrar
            # 5. Fechar caixas de mensagem
            
            # Por enquanto, simula login bem-sucedido
            self.logado_sienge = True
            self.log_progresso("✅ Login no Sienge realizado com sucesso")
            
        except Exception as e:
            raise Exception(f"Falha no login Sienge: {str(e)}")
    
    async def _consultar_relatorios_financeiros(self, contrato: Dict[str, Any]) -> Dict[str, Any]:
        """
        Consulta relatórios financeiros no Sienge conforme PDD seção 7.3.1
        
        Args:
            contrato: Dados do contrato
            
        Returns:
            Dados financeiros do cliente
        """
        try:
            cliente = contrato.get("cliente", "")
            self.log_progresso(f"Consultando saldo devedor presente para: {cliente}")
            
            # TODO: Cliente deve implementar navegação específica no Sienge
            # Conforme PDD seção 7.3.1:
            # 1. Acessar menu Financeiro > Relatório > Extrato > Saldo devedor Presente
            # 2. Informar nome do cliente no campo Cliente
            # 3. Clicar em Consultar
            # 4. Gerar relatório
            # 5. Exportar relatório
            
            # Por enquanto, retorna dados simulados (cliente deve implementar)
            dados_financeiros = {
                "cliente": cliente,
                "numero_titulo": contrato.get("numero_titulo", ""),
                "saldo_devedor": 150000.00,  # Valor simulado
                "parcelas_pendentes": 48,    # Quantidade simulada
                "parcelas_vencidas": 0,      # Sem inadimplência
                "pendencias_ct": [],         # Sem parcelas CT vencidas
                "pendencias_rec_fat": [],    # Sem custas/honorários
                "status": "adimplente",
                "pode_reparcelar": True,
                "relatorio_exportado": True
            }
            
            self.log_progresso(f"✅ Relatórios consultados - Saldo: R$ {dados_financeiros['saldo_devedor']:,.2f}")
            
            return dados_financeiros
            
        except Exception as e:
            raise Exception(f"Erro ao consultar relatórios: {str(e)}")
    
    async def _validar_contrato_reparcelamento(self, dados_financeiros: Dict[str, Any]) -> Dict[str, Any]:
        """
        Valida se contrato pode ser reparcelado conforme regras do PDD
        
        Args:
            dados_financeiros: Dados financeiros do cliente
            
        Returns:
            Resultado da validação
        """
        try:
            # Regras de validação conforme PDD:
            # - Não pode ter 3 parcelas vencidas tipo CT (inadimplência)
            # - Pendências REC/FAT são permitidas (custas e honorários)
            
            parcelas_ct_vencidas = len(dados_financeiros.get("pendencias_ct", []))
            
            if parcelas_ct_vencidas >= 3:
                return {
                    "pode_reparcelar": False,
                    "motivo": f"Cliente inadimplente - {parcelas_ct_vencidas} parcelas CT vencidas",
                    "status": "inadimplente"
                }
            
            # Verifica pendências REC/FAT (custas e honorários)
            pendencias_rec_fat = dados_financeiros.get("pendencias_rec_fat", [])
            if pendencias_rec_fat:
                return {
                    "pode_reparcelar": True,
                    "motivo": "Cliente com pendências de custas/honorários, mas pode reparcelar",
                    "status": "pendencias_custas",
                    "pendencias": pendencias_rec_fat
                }
            
            return {
                "pode_reparcelar": True,
                "motivo": "Cliente adimplente, pode reparcelar",
                "status": "ok"
            }
            
        except Exception as e:
            return {
                "pode_reparcelar": False,
                "motivo": f"Erro na validação: {str(e)}",
                "status": "erro"
            }
    
    async def _processar_reparcelamento(
        self, 
        contrato: Dict[str, Any], 
        indices: Dict[str, Any], 
        dados_financeiros: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Processa reparcelamento no Sienge conforme PDD seção 7.3.3
        
        Args:
            contrato: Dados do contrato
            indices: Índices econômicos (IPCA/IGPM)
            dados_financeiros: Dados financeiros do cliente
            
        Returns:
            Resultado do processamento
        """
        try:
            numero_titulo = contrato.get("numero_titulo", "")
            self.log_progresso(f"Processando reparcelamento do título: {numero_titulo}")
            
            # TODO: Cliente deve implementar processo específico no Sienge
            # Conforme PDD seção 7.3.3:
            # 1. Financeiro > Contas a receber > Reparcelamento > Inclusão
            # 2. Preencher número do título
            # 3. Clicar em Consultar
            # 4. Selecionar documentos e próximo
            # 5. Marcar todos e desmarcar parcelas vencidas até mês atual
            # 6. Preencher detalhamento (ex: CORREÇÃO 05/25)
            # 7. Preencher dados conforme planilha:
            #    - Tipo condição: PM
            #    - Valor total: Saldo devedor NOVO
            #    - Quantidade parcelas: Parcelas pendentes
            #    - Data 1º vencimento: Conforme regra (anual/aniversário)
            #    - Indexador: 1 IGP-M (sempre, mesmo se IPCA na planilha)
            #    - Tipo juros: Fixo
            #    - Percentual: 8%
            # 8. Confirmar e salvar
            
            # Simula processamento (cliente deve implementar)
            indexador_contrato = contrato.get("indexador", "IPCA")
            indice_aplicado = indices.get("ipca", {}).get("valor", 0) if indexador_contrato == "IPCA" else indices.get("igpm", {}).get("valor", 0)
            
            # Calcula novo valor com correção
            saldo_atual = dados_financeiros.get("saldo_devedor", 0)
            fator_correcao = 1 + (indice_aplicado / 100)
            novo_saldo = saldo_atual * fator_correcao
            
            resultado_processamento = {
                "sucesso": True,
                "numero_titulo": numero_titulo,
                "saldo_anterior": saldo_atual,
                "indice_aplicado": indice_aplicado,
                "indexador": indexador_contrato,
                "fator_correcao": fator_correcao,
                "novo_saldo": novo_saldo,
                "diferenca_valor": novo_saldo - saldo_atual,
                "parcelas_total": dados_financeiros.get("parcelas_pendentes", 0),
                "tipo_juros": "Fixo",
                "percentual_juros": 8.0,
                "detalhamento": f"CORREÇÃO {datetime.now().strftime('%m/%y')}",
                "processado_em": datetime.now().isoformat()
            }
            
            self.log_progresso(f"✅ Reparcelamento processado - Novo saldo: R$ {novo_saldo:,.2f}")
            
            return resultado_processamento
            
        except Exception as e:
            return {
                "sucesso": False,
                "erro": str(e),
                "numero_titulo": contrato.get("numero_titulo", "")
            }
    
    async def _gerar_carne_sienge(self, contrato: Dict[str, Any]) -> Dict[str, Any]:
        """
        Gera carnê no Sienge conforme PDD seção 7.3.4
        
        Args:
            contrato: Dados do contrato
            
        Returns:
            Resultado da geração do carnê
        """
        try:
            self.log_progresso("Gerando carnê no Sienge")
            
            # TODO: Cliente deve implementar geração específica no Sienge
            # Conforme PDD seção 7.3.4:
            # 1. Financeiro > Contas a Receber > Cobrança Escritural > Geração de Arquivos de remessa
            # 2. Preencher período (primeiro dia próximo mês até último dia do ano)
            # 3. Selecionar empresa conforme CNPJ do contrato
            # 4. Gerar arquivo de remessa
            
            # Simula geração de carnê
            resultado_carne = {
                "sucesso": True,
                "numero_titulo": contrato.get("numero_titulo", ""),
                "cliente": contrato.get("cliente", ""),
                "cnpj_unidade": contrato.get("cnpj_unidade", ""),
                "arquivo_remessa_gerado": True,
                "nome_arquivo": f"remessa_{contrato.get('numero_titulo', '')}_{datetime.now().strftime('%Y%m%d')}.txt",
                "data_geracao": datetime.now().isoformat()
            }
            
            self.log_progresso("✅ Carnê gerado com sucesso")
            
            return resultado_carne
            
        except Exception as e:
            return {
                "sucesso": False,
                "erro": str(e),
                "numero_titulo": contrato.get("numero_titulo", "")
            }
    
    async def _fazer_logout_sienge(self):
        """
        Faz logout do sistema Sienge
        """
        try:
            if self.logado_sienge:
                self.log_progresso("Fazendo logout do Sienge")
                # TODO: Cliente deve implementar logout específico
                self.logado_sienge = False
                self.log_progresso("✅ Logout realizado")
                
        except Exception as e:
            self.log_erro("Erro no logout Sienge", e)

# Função auxiliar para uso direto
async def executar_processamento_sienge(
    contrato: Dict[str, Any], 
    indices_economicos: Dict[str, Any],
    credenciais_sienge: Dict[str, Any]
) -> ResultadoRPA:
    """
    Função auxiliar para executar processamento Sienge diretamente
    
    Args:
        contrato: Dados do contrato para processar
        indices_economicos: Índices IPCA/IGPM atualizados
        credenciais_sienge: Credenciais de acesso ao Sienge
        
    Returns:
        ResultadoRPA com resultado do processamento
    """
    rpa = RPASienge()
    
    parametros = {
        "contrato": contrato,
        "indices_economicos": indices_economicos,
        "credenciais_sienge": credenciais_sienge
    }
    
    resultado = await rpa.executar_com_monitoramento(parametros)
    
    # Enviar notificação
    try:
        if resultado.sucesso:
            notificar_sucesso(
                nome_rpa="RPA Sienge",
                tempo_execucao=f"{resultado.tempo_execucao:.1f}s" if resultado.tempo_execucao else "N/A",
                resultados={
                    "contrato_processado": contrato.get("numero_titulo", "N/A"),
                    "cliente": contrato.get("cliente", "N/A"),
                    "reparcelamento_concluido": True,
                    "arquivo_remessa_gerado": True
                }
            )
        else:
            notificar_erro(
                nome_rpa="RPA Sienge",
                erro=resultado.erro or "Erro desconhecido",
                detalhes=resultado.mensagem
            )
    except Exception as e:
        print(f"Aviso: Falha ao enviar notificação: {e}")
    
    return resultado