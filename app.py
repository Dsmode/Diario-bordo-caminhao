import os
import json
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
from flask_sqlalchemy import SQLAlchemy

app = Flask(__name__)

app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'chave-secreta-diario-de-bordo')
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL', 'sqlite:///diario_bordo.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# ==============================================================================
# MODELOS DO BANCO DE DADOS
# ==============================================================================

class Jogador(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(100), default="Motorista")
    empresa_base = db.Column(db.String(100), default="Swift Transportation")
    cidade_base = db.Column(db.String(100), default="Los Angeles")
    fase = db.Column(db.Integer, default=1)
    cargo = db.Column(db.String(100), default="Empregado")
    moeda = db.Column(db.String(10), default="$")
    saldo = db.Column(db.Float, default=0.0)
    total_salarios = db.Column(db.Float, default=0.0)
    dias_trabalhados = db.Column(db.Integer, default=1)
    ciclo = db.Column(db.Integer, default=1)
    confirmar_voltar_dia = db.Column(db.Boolean, default=True)
    dias_globais = db.Column(db.Integer, default=1)
    empresa_bloqueada = db.Column(db.String(100), nullable=True)
    dia_global_desbloqueio = db.Column(db.Integer, nullable=True)

    @property
    def dias_no_mes(self):
        return 30 if (self.ciclo % 2 != 0) else 31

class Viagem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    origem = db.Column(db.String(100), nullable=False)
    destino = db.Column(db.String(100), nullable=False)
    frete_bruto = db.Column(db.Float, nullable=False)
    distancia_km = db.Column(db.Float, nullable=False)
    avaria_pct = db.Column(db.Float, default=0.0)
    comissao_recebida = db.Column(db.Float, nullable=False)
    anotacoes = db.Column(db.String(255), nullable=True)
    
    # NOVAS COLUNAS: Atrela a viagem ao dia e ciclo em que foi feita
    numero_dia = db.Column(db.Integer, default=1)
    ciclo = db.Column(db.Integer, default=1)

class DiaHistorico(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    numero_dia = db.Column(db.Integer, nullable=False)
    ciclo = db.Column(db.Integer, nullable=False)
    situacao = db.Column(db.String(50), default="Tranquilo")
    chuva = db.Column(db.String(50), default="Sem chuva")
    
    custo_total = db.Column(db.Float, default=0.0)
    # NOVA COLUNA: Salva todo o ganho consolidado deste dia
    ganho_total = db.Column(db.Float, default=0.0)
    
    eventos = db.relationship('EventoDia', backref='dia_historico', lazy=True, cascade="all, delete")

class EventoDia(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    hora = db.Column(db.String(10), nullable=False)
    tipo = db.Column(db.String(50), nullable=False)
    cidade = db.Column(db.String(100), nullable=False)
    valor = db.Column(db.Float, default=0.0)
    em_servico = db.Column(db.Boolean, default=False)
    observacao = db.Column(db.String(255), nullable=True)
    fase_jogador = db.Column(db.Integer, default=1) 
    dia_historico_id = db.Column(db.Integer, db.ForeignKey('dia_historico.id'), nullable=True)

# ==============================================================================
# FILTROS E FUNÇÕES AUXILIARES
# ==============================================================================

@app.template_filter('moeda')
def moeda_filter(valor, simbolo='$'):
    if valor is None: valor = 0.0
    sinal = '-' if valor < 0 else ''
    return f"{sinal}{simbolo} {abs(valor):,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.')

@app.template_filter('numero')
def numero_filter(valor, casas=0):
    if valor is None: valor = 0
    if casas == 0: return f"{int(valor):,}".replace(',', '.')
    else: return f"{{:,.{casas}f}}".format(valor).replace(',', 'X').replace('.', ',').replace('X', '.')

def parse_br_float(texto):
    if not texto: return 0.0
    try: return float(str(texto).replace('.', '').replace(',', '.'))
    except ValueError: return 0.0

def obter_pct_comissao(fase):
    return 0.05 if fase == 1 else (0.10 if fase == 2 else 0.20)

def obter_cargo_padrao_fase(fase):
    return {1: "Empregado", 2: "Agregado", 3: "Autônomo", 4: "Empresário"}.get(fase, "Empregado")

def fechar_dia_jogador(jogador):
    eventos_pendentes = EventoDia.query.filter_by(dia_historico_id=None).all()
    custo_dia = sum(ev.valor for ev in eventos_pendentes if (ev.fase_jogador >= 3) or (not ev.em_servico))
    jogador.saldo -= custo_dia

    viagens_do_dia = Viagem.query.filter_by(numero_dia=jogador.dias_trabalhados, ciclo=jogador.ciclo).all()
    ganho_dia = sum(v.comissao_recebida for v in viagens_do_dia)

    if jogador.dias_trabalhados == jogador.dias_no_mes:
        salario = 1300.0 if jogador.fase == 1 else (1500.0 if jogador.fase == 2 else 0.0)
        ganho_dia += salario
        jogador.saldo += salario
        jogador.total_salarios += salario

    novo_dia = DiaHistorico(
        numero_dia=jogador.dias_trabalhados, 
        ciclo=jogador.ciclo, 
        custo_total=custo_dia,
        ganho_total=ganho_dia
    )
    db.session.add(novo_dia)
    db.session.flush()

    for ev in eventos_pendentes: 
        ev.dia_historico_id = novo_dia.id

    jogador.dias_trabalhados += 1
    if jogador.dias_trabalhados > jogador.dias_no_mes:
        jogador.dias_trabalhados = 1
        jogador.ciclo += 1

def fechar_dia_jogador(jogador):
    eventos_pendentes = EventoDia.query.filter_by(dia_historico_id=None).all()
    custo_dia = sum(ev.valor for ev in eventos_pendentes if (ev.fase_jogador >= 3) or (not ev.em_servico))
    jogador.saldo -= custo_dia

    viagens_do_dia = Viagem.query.filter_by(numero_dia=jogador.dias_trabalhados, ciclo=jogador.ciclo).all()
    ganho_dia = sum(v.comissao_recebida for v in viagens_do_dia)

    if jogador.dias_trabalhados == jogador.dias_no_mes:
        salario = 1300.0 if jogador.fase == 1 else (1500.0 if jogador.fase == 2 else 0.0)
        ganho_dia += salario
        jogador.saldo += salario
        jogador.total_salarios += salario

    novo_dia = DiaHistorico(numero_dia=jogador.dias_trabalhados, ciclo=jogador.ciclo, custo_total=custo_dia, ganho_total=ganho_dia)
    db.session.add(novo_dia)
    db.session.flush()

    for ev in eventos_pendentes: ev.dia_historico_id = novo_dia.id

    jogador.dias_trabalhados += 1
    jogador.dias_globais += 1 # ACRESCENTA O DIA GLOBAL
    if jogador.dias_trabalhados > jogador.dias_no_mes:
        jogador.dias_trabalhados = 1
        jogador.ciclo += 1

def aplicar_dias_inativos(jogador, qtd_dias, observacao_dia, tipo_override=None):
    custos_diarios = [
        ("08:00", "Refeição", "Café da Manhã", 15.0),
        ("13:00", "Refeição", "Almoço", 25.0),
        ("20:00", "Refeição", "Jantar", 20.0),
        ("22:00", "Descanso/11h", "Estadia", 45.0)
    ]
    
    eventos_pendentes = EventoDia.query.filter_by(dia_historico_id=None).all()
    if eventos_pendentes:
        fechar_dia_jogador(jogador)
        db.session.flush()

    for _ in range(qtd_dias):
        custo_dia = sum(c[3] for c in custos_diarios)
        novo_dia = DiaHistorico(numero_dia=jogador.dias_trabalhados, ciclo=jogador.ciclo, situacao=observacao_dia, chuva="Sem chuva", custo_total=custo_dia, ganho_total=0.0)
        db.session.add(novo_dia)
        db.session.flush()
        
        for hora, tipo_base, obs, valor in custos_diarios:
            tipo_final = tipo_override if tipo_override else tipo_base
            ev = EventoDia(hora=hora, tipo=tipo_final, cidade=jogador.cidade_base, valor=valor, em_servico=False, observacao=obs, fase_jogador=jogador.fase, dia_historico_id=novo_dia.id)
            db.session.add(ev)
            
        jogador.saldo -= custo_dia
        jogador.dias_trabalhados += 1
        jogador.dias_globais += 1 # ACRESCENTA O DIA GLOBAL A CADA GIRO DO LOOP
        if jogador.dias_trabalhados > jogador.dias_no_mes:
            jogador.dias_trabalhados = 1
            jogador.ciclo += 1
            salario = 1300.0 if jogador.fase == 1 else (1500.0 if jogador.fase == 2 else 0.0)
            jogador.saldo += salario
            jogador.total_salarios += salario

# ==============================================================================
# ROTAS DA APLICAÇÃO
# ==============================================================================

@app.route('/')
def dashboard():
    jogador = Jogador.query.first()
    if not jogador:
        jogador = Jogador(saldo=5000.0)
        db.session.add(jogador)
        db.session.commit()

    total_comissoes = db.session.query(db.func.sum(Viagem.comissao_recebida)).scalar() or 0.0
    viagens = Viagem.query.order_by(Viagem.id.desc()).limit(7).all()
    historico_dias = DiaHistorico.query.order_by(DiaHistorico.ciclo.desc(), DiaHistorico.numero_dia.desc(), DiaHistorico.id.desc()).limit(7).all()
    eventos_pendentes = EventoDia.query.filter_by(dia_historico_id=None).order_by(EventoDia.id.asc()).all()

    return render_template('dashboard.html', jogador=jogador, viagens=viagens, total_comissoes=total_comissoes, eventos_pendentes=eventos_pendentes, historico_dias=historico_dias, aba_ativa='painel')

@app.route('/calculadora')
def calculadora():
    jogador = Jogador.query.first()
    if not jogador: return redirect(url_for('dashboard'))
    return render_template('calculadora.html', jogador=jogador, aba_ativa='calculadora')

@app.route('/comprar_passagem', methods=['POST'])
def comprar_passagem():
    jogador = Jogador.query.first()
    if not jogador: return redirect(url_for('dashboard'))

    origem = request.form.get('origem')
    destino = request.form.get('destino')
    valor = parse_br_float(request.form.get('valor'))
    minutos_viagem = int(request.form.get('tempo_minutos', 0))

    ultimo_evento = EventoDia.query.filter_by(dia_historico_id=None).order_by(EventoDia.id.desc()).first()
    if ultimo_evento:
        h, m = map(int, ultimo_evento.hora.split(':'))
        minutos_atual = (h * 60) + m
    else:
        minutos_atual = 8 * 60

    minutos_final = minutos_atual + minutos_viagem

    if minutos_final < 1440:
        hora_chegada = f"{minutos_final // 60:02d}:{minutos_final % 60:02d}"
        novo_evento = EventoDia(hora=hora_chegada, tipo="Deslocamento (Passagem)", cidade=f"{origem} ➔ {destino}", valor=valor, em_servico=False, observacao=f"Viagem de ônibus ({minutos_viagem//60}h {minutos_viagem%60}m)", fase_jogador=jogador.fase)
        db.session.add(novo_evento)
    else:
        evento_embarque = EventoDia(hora="23:59", tipo="Deslocamento (Embarque)", cidade=origem, valor=valor, em_servico=False, observacao="Passagem cobrada. Viagem entrou pela madrugada.", fase_jogador=jogador.fase)
        db.session.add(evento_embarque)
        db.session.flush()

        fechar_dia_jogador(jogador)

        minutos_novo_dia = minutos_final - 1440
        hora_chegada_novo_dia = f"{minutos_novo_dia // 60:02d}:{minutos_novo_dia % 60:02d}"
        evento_desembarque = EventoDia(hora=hora_chegada_novo_dia, tipo="Deslocamento (Chegada)", cidade=destino, valor=0.0, em_servico=False, observacao=f"Fim da viagem saindo de {origem}.", fase_jogador=jogador.fase)
        db.session.add(evento_desembarque)

    db.session.commit()
    return redirect(url_for('dashboard'))

@app.route('/estatisticas')
def estatisticas():
    jogador = Jogador.query.first()
    if not jogador: return redirect(url_for('dashboard'))

    viagens = Viagem.query.all()
    total_km = sum(v.distancia_km for v in viagens)
    lucro_por_km = (sum(v.comissao_recebida for v in viagens) / total_km) if total_km > 0 else 0
    maior_frete = max(viagens, key=lambda v: v.comissao_recebida) if viagens else None

    eventos_pagos = EventoDia.query.filter(db.or_(EventoDia.fase_jogador >= 3, EventoDia.em_servico == False)).all()
    custo_desatencao = sum(ev.valor for ev in eventos_pagos if ev.tipo in ['Multa', 'Acidente']) + sum(v.frete_bruto * (v.avaria_pct / 100.0) for v in viagens)

    despesas_agrupadas = {}
    for ev in eventos_pagos:
        if ev.valor > 0: despesas_agrupadas[ev.tipo] = despesas_agrupadas.get(ev.tipo, 0) + ev.valor

    ultimas_viagens = Viagem.query.order_by(Viagem.id.desc()).limit(7).all()
    ultimas_viagens.reverse()
    fretes_labels = [f"{v.origem} ➔ {v.destino}" for v in ultimas_viagens]
    fretes_valores = [v.comissao_recebida for v in ultimas_viagens]

    ultimos_dias = DiaHistorico.query.order_by(DiaHistorico.ciclo.desc(), DiaHistorico.numero_dia.desc(), DiaHistorico.id.desc()).limit(10).all()
    ultimos_dias.reverse()
    dias_labels = [f"Dia {d.numero_dia}" for d in ultimos_dias]
    dias_custos = [d.custo_total for d in ultimos_dias]
    
    # NOVA VARIÁVEL: Lista com os ganhos enviados para o gráfico!
    dias_ganhos = [d.ganho_total for d in ultimos_dias]

    dados_graficos = {
        'despesas_labels': list(despesas_agrupadas.keys()), 'despesas_valores': list(despesas_agrupadas.values()),
        'fretes_labels': fretes_labels, 'fretes_valores': fretes_valores,
        'dias_labels': dias_labels, 'dias_custos': dias_custos, 'dias_ganhos': dias_ganhos
    }

    return render_template('estatisticas.html', jogador=jogador, aba_ativa='estatisticas', total_km=total_km, lucro_por_km=lucro_por_km, custo_desatencao=custo_desatencao, maior_frete=maior_frete, dados_graficos=json.dumps(dados_graficos))

@app.route('/registrar_viagem', methods=['POST'])
def registrar_viagem():
    jogador = Jogador.query.first()
    if not jogador: return redirect(url_for('dashboard'))

    origem, destino = request.form.get('origem'), request.form.get('destino')
    frete_bruto, distancia_km = parse_br_float(request.form.get('frete_bruto')), parse_br_float(request.form.get('distancia_km'))
    avaria_pct = parse_br_float(request.form.get('avaria_pct'))
    
    comissao_bruta = frete_bruto * obter_pct_comissao(jogador.fase)
    saldo_diferenca = comissao_bruta - (frete_bruto * (avaria_pct / 100.0))
    comissao_liquida = saldo_diferenca / 2.0 if saldo_diferenca < 0 else saldo_diferenca

    jogador.saldo += comissao_liquida
    
    # Passando o carimbo de tempo para a Viagem
    nova_viagem = Viagem(origem=origem, destino=destino, frete_bruto=frete_bruto, distancia_km=distancia_km, avaria_pct=avaria_pct, comissao_recebida=comissao_liquida, anotacoes=request.form.get('anotacoes'), numero_dia=jogador.dias_trabalhados, ciclo=jogador.ciclo)
    db.session.add(nova_viagem)
    db.session.commit()
    return redirect(url_for('dashboard'))

@app.route('/registrar_evento', methods=['POST'])
def registrar_evento():
    jogador = Jogador.query.first()
    novo_evento = EventoDia(hora=request.form.get('hora'), tipo=request.form.get('tipo'), cidade=request.form.get('cidade'), valor=parse_br_float(request.form.get('valor')), em_servico=True if request.form.get('em_servico') == 'on' else False, observacao=request.form.get('observacao'), fase_jogador=jogador.fase if jogador else 1, dia_historico_id=None)
    db.session.add(novo_evento)
    db.session.commit()
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest': return jsonify({"status": "success"})
    return redirect(url_for('dashboard'))

@app.route('/excluir_evento/<int:id_evento>', methods=['POST'])
def excluir_evento(id_evento):
    evento = EventoDia.query.get_or_404(id_evento)
    if evento.dia_historico_id is None:
        db.session.delete(evento)
        db.session.commit()
    return redirect(url_for('dashboard'))

@app.route('/lancar_dia', methods=['POST'])
def lancar_dia():
    jogador = Jogador.query.first()
    if jogador:
        fechar_dia_jogador(jogador)
        db.session.commit()
    return redirect(url_for('dashboard'))

@app.route('/avancar_dia', methods=['POST'])
def avancar_dia():
    jogador = Jogador.query.first()
    if jogador:
        fechar_dia_jogador(jogador)
        db.session.commit()
    return redirect(url_for('dashboard'))

@app.route('/voltar_dia', methods=['POST'])
def voltar_dia():
    jogador = Jogador.query.first()
    if not jogador: return redirect(url_for('dashboard'))
    
    if request.form.get('nao_perguntar_mais') == 'on': jogador.confirmar_voltar_dia = False
    
    if jogador.dias_trabalhados == 1 and jogador.ciclo == 1:
        db.session.commit()
        return redirect(url_for('dashboard'))

    jogador.dias_trabalhados -= 1
    jogador.dias_globais -= 1 # DIMINUI O DIA GLOBAL (Assim o bloqueio de 30 dias respeita a viagem no tempo!)
    if jogador.dias_trabalhados < 1:
        jogador.ciclo -= 1
        jogador.dias_trabalhados = jogador.dias_no_mes
        salario = 1300.0 if jogador.fase == 1 else (1500.0 if jogador.fase == 2 else 0.0)
        jogador.saldo -= salario
        jogador.total_salarios -= salario

    dias_para_desfazer = DiaHistorico.query.filter_by(numero_dia=jogador.dias_trabalhados, ciclo=jogador.ciclo).all()
    for dia in dias_para_desfazer:
        jogador.saldo += dia.custo_total
        for ev in dia.eventos: ev.dia_historico_id = None
        db.session.delete(dia)

    db.session.commit()
    return redirect(url_for('dashboard'))

@app.route('/excluir_viagem/<int:id_viagem>', methods=['POST'])
def excluir_viagem(id_viagem):
    viagem = Viagem.query.get_or_404(id_viagem)
    jogador = Jogador.query.first()
    if jogador and viagem:
        jogador.saldo -= viagem.comissao_recebida
        db.session.delete(viagem)
        db.session.commit()
    return redirect(url_for('dashboard'))

@app.route('/limpar_viagens', methods=['POST'])
def limpar_viagens():
    for viagem in Viagem.query.all():
        Jogador.query.first().saldo -= viagem.comissao_recebida
        db.session.delete(viagem)
    db.session.commit()
    return redirect(url_for('dashboard'))

@app.route('/excluir_dia/<int:id_dia>', methods=['POST'])
def excluir_dia(id_dia):
    dia = DiaHistorico.query.get_or_404(id_dia)
    jogador = Jogador.query.first()
    if jogador and dia:
        jogador.saldo += dia.custo_total
        db.session.delete(dia)
        db.session.commit()
    return redirect(url_for('dashboard'))

@app.route('/limpar_historico', methods=['POST'])
def limpar_historico():
    for dia in DiaHistorico.query.all():
        Jogador.query.first().saldo += dia.custo_total
        db.session.delete(dia)
    db.session.commit()
    return redirect(url_for('dashboard'))

@app.route('/lancar_fds', methods=['POST'])
def lancar_fds():
    jogador = Jogador.query.first()
    if jogador:
        # Fim de semana usa as categorias normais (Refeição e Descanso)
        aplicar_dias_inativos(jogador, 2, "Final de Semana")
        db.session.commit()
    return redirect(url_for('dashboard'))

@app.route('/caminhao_tombado', methods=['POST'])
def caminhao_tombado():
    jogador = Jogador.query.first()
    if jogador:
        if jogador.empresa_base != "Desempregado":
            # Guarda a empresa antiga e seta a data de desbloqueio para 30 dias no futuro!
            jogador.empresa_bloqueada = jogador.empresa_base
            jogador.dia_global_desbloqueio = jogador.dias_globais + 30
            
        jogador.empresa_base = "Desempregado"
        jogador.cargo = "Desempregado"
        aplicar_dias_inativos(jogador, 10, "Demissão / Busca de Emprego", tipo_override="Acidente")
        db.session.commit()
    return redirect(url_for('dashboard'))

@app.route('/empresa')
def empresa():
    jogador = Jogador.query.first()
    if not jogador: return redirect(url_for('dashboard'))
    return render_template('empresa.html', jogador=jogador, aba_ativa='empresa')

@app.route('/salvar_empresa', methods=['POST'])
def salvar_empresa():
    jogador = Jogador.query.first()
    if jogador:
        nova_empresa = request.form.get('empresa_base', jogador.empresa_base)
        
        # VERIFICAÇÃO DO BLOQUEIO DE 30 DIAS
        if jogador.empresa_bloqueada and nova_empresa.lower().strip() == jogador.empresa_bloqueada.lower().strip():
            if jogador.dias_globais < jogador.dia_global_desbloqueio:
                return redirect(url_for('empresa')) # Ignora a mudança e volta pra tela de empresa
                
        jogador.empresa_base = nova_empresa
        jogador.cidade_base = request.form.get('cidade_base', jogador.cidade_base)
        if jogador.empresa_base != "Desempregado":
            jogador.cargo = obter_cargo_padrao_fase(jogador.fase)
        db.session.commit()
    # AGORA REDIRECIONA PARA O PAINEL PRINCIPAL
    return redirect(url_for('dashboard'))

@app.route('/opcoes', methods=['GET', 'POST'])
@app.route('/salvar_opcoes', methods=['POST'])
def opcoes():
    jogador = Jogador.query.first()
    if not jogador: db.session.add(Jogador())
    if request.method == 'POST':
        jogador.nome = request.form.get('nome', jogador.nome)
        jogador.fase = int(request.form.get('fase', jogador.fase))
        jogador.cargo = obter_cargo_padrao_fase(jogador.fase)
        jogador.moeda = request.form.get('moeda', jogador.moeda)
        jogador.confirmar_voltar_dia = True if request.form.get('confirmar_voltar_dia') == 'on' else False
        db.session.commit()
        return redirect(url_for('dashboard'))
    return render_template('opcoes.html', jogador=jogador, aba_ativa='opcoes')

if __name__ == '__main__':
    with app.app_context(): db.create_all()
    app.run(debug=True)