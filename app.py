import os
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
from flask_sqlalchemy import SQLAlchemy

app = Flask(__name__)

# Configurações de Segurança e Banco de Dados
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


class DiaHistorico(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    numero_dia = db.Column(db.Integer, nullable=False)
    ciclo = db.Column(db.Integer, nullable=False)
    situacao = db.Column(db.String(50), default="Tranquilo")
    chuva = db.Column(db.String(50), default="Sem chuva")
    custo_total = db.Column(db.Float, default=0.0)
    eventos = db.relationship('EventoDia', backref='dia_historico', lazy=True, cascade="all, delete")


class EventoDia(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    hora = db.Column(db.String(10), nullable=False)
    tipo = db.Column(db.String(50), nullable=False)
    cidade = db.Column(db.String(100), nullable=False)
    valor = db.Column(db.Float, default=0.0)
    em_servico = db.Column(db.Boolean, default=False)
    observacao = db.Column(db.String(255), nullable=True)
    dia_historico_id = db.Column(db.Integer, db.ForeignKey('dia_historico.id'), nullable=True)


# ==============================================================================
# FILTROS JINJA CUSTOMIZADOS E FUNÇÕES
# ==============================================================================

@app.template_filter('moeda')
def moeda_filter(valor, simbolo='$'):
    if valor is None:
        valor = 0.0
    sinal = '-' if valor < 0 else ''
    valor_abs = abs(valor)
    valor_formatado = f"{valor_abs:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.')
    return f"{sinal}{simbolo} {valor_formatado}"

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
    if fase == 1: return 0.05
    elif fase == 2: return 0.10
    else: return 0.20

def obter_cargo_padrao_fase(fase):
    cargos = {1: "Empregado", 2: "Agregado", 3: "Autônomo", 4: "Empresário"}
    return cargos.get(fase, "Empregado")

# ==============================================================================
# ROTAS DA APLICAÇÃO
# ==============================================================================

@app.route('/')
def dashboard():
    jogador = Jogador.query.first()
    if not jogador:
        # CORREÇÃO: total_salarios=0.0 para não contar o valor inicial, e saldo=5000.0 como manda a regra realista!
        jogador = Jogador(nome="Carlos Oliveira", empresa_base="Swift Transportation", cidade_base="Los Angeles", fase=1, cargo="Empregado", moeda="$", saldo=5000.0, total_salarios=0.0, dias_trabalhados=1, ciclo=1)
        db.session.add(jogador)
        db.session.commit()

    viagens = Viagem.query.order_by(Viagem.id.desc()).all()
    eventos_pendentes = EventoDia.query.filter_by(dia_historico_id=None).order_by(EventoDia.id.asc()).all()
    historico_dias = DiaHistorico.query.order_by(DiaHistorico.id.desc()).all()

    return render_template('dashboard.html', jogador=jogador, viagens=viagens, eventos_pendentes=eventos_pendentes, historico_dias=historico_dias, aba_ativa='painel')


@app.route('/registrar_viagem', methods=['POST'])
def registrar_viagem():
    jogador = Jogador.query.first()
    if not jogador: return redirect(url_for('dashboard'))

    origem = request.form.get('origem')
    destino = request.form.get('destino')
    frete_bruto = parse_br_float(request.form.get('frete_bruto'))
    distancia_km = parse_br_float(request.form.get('distancia_km'))
    avaria_pct = parse_br_float(request.form.get('avaria_pct'))
    anotacoes = request.form.get('anotacoes')

    comissao_bruta = frete_bruto * obter_pct_comissao(jogador.fase)
    desconto_avaria = frete_bruto * (avaria_pct / 100.0)
    saldo_diferenca = comissao_bruta - desconto_avaria
    comissao_liquida = saldo_diferenca / 2.0 if saldo_diferenca < 0 else saldo_diferenca

    jogador.saldo += comissao_liquida

    nova_viagem = Viagem(origem=origem, destino=destino, frete_bruto=frete_bruto, distancia_km=distancia_km, avaria_pct=avaria_pct, comissao_recebida=comissao_liquida, anotacoes=anotacoes)
    db.session.add(nova_viagem)
    db.session.commit()
    return redirect(url_for('dashboard'))


@app.route('/registrar_evento', methods=['POST'])
def registrar_evento():
    novo_evento = EventoDia(
        hora=request.form.get('hora'),
        tipo=request.form.get('tipo'),
        cidade=request.form.get('cidade'),
        valor=parse_br_float(request.form.get('valor')),
        em_servico=True if request.form.get('em_servico') == 'on' else False,
        observacao=request.form.get('observacao'),
        dia_historico_id=None
    )
    db.session.add(novo_evento)
    db.session.commit()

    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return jsonify({"status": "success"})
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
    eventos_pendentes = EventoDia.query.filter_by(dia_historico_id=None).all()
    if not jogador: return redirect(url_for('dashboard'))

    custo_dia = sum(ev.valor for ev in eventos_pendentes if (jogador.fase >= 3) or (not ev.em_servico))
    jogador.saldo -= custo_dia

    novo_dia = DiaHistorico(numero_dia=jogador.dias_trabalhados, ciclo=jogador.ciclo, situacao="Tranquilo", chuva="Sem chuva", custo_total=custo_dia)
    db.session.add(novo_dia)
    db.session.flush()

    for ev in eventos_pendentes: ev.dia_historico_id = novo_dia.id

    jogador.dias_trabalhados += 1
    if jogador.dias_trabalhados > jogador.dias_no_mes:
        jogador.dias_trabalhados = 1
        jogador.ciclo += 1
        salario = 1300.0 if jogador.fase == 1 else (1500.0 if jogador.fase == 2 else 0.0)
        jogador.saldo += salario
        jogador.total_salarios += salario

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
    viagens = Viagem.query.all()
    jogador = Jogador.query.first()
    if jogador:
        for viagem in viagens:
            jogador.saldo -= viagem.comissao_recebida  # Estorna as comissões no saldo
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
    dias = DiaHistorico.query.all()
    jogador = Jogador.query.first()
    if jogador:
        for dia in dias:
            jogador.saldo += dia.custo_total
            db.session.delete(dia)
        db.session.commit()
    return redirect(url_for('dashboard'))


@app.route('/avancar_dia', methods=['POST'])
def avancar_dia():
    jogador = Jogador.query.first()
    if jogador:
        jogador.dias_trabalhados += 1
        if jogador.dias_trabalhados > jogador.dias_no_mes:
            jogador.dias_trabalhados = 1
            jogador.ciclo += 1
            salario = 1300.0 if jogador.fase == 1 else (1500.0 if jogador.fase == 2 else 0.0)
            jogador.saldo += salario
            jogador.total_salarios += salario
        db.session.commit()
    return redirect(url_for('dashboard'))


@app.route('/opcoes', methods=['GET', 'POST'])
@app.route('/salvar_opcoes', methods=['POST'])
def opcoes():
    jogador = Jogador.query.first()
    if not jogador:
        jogador = Jogador()
        db.session.add(jogador)

    if request.method == 'POST':
        jogador.nome = request.form.get('nome', jogador.nome)
        jogador.empresa_base = request.form.get('empresa_base', jogador.empresa_base)
        jogador.cidade_base = request.form.get('cidade_base', jogador.cidade_base)
        nova_fase = int(request.form.get('fase', jogador.fase))
        jogador.fase = nova_fase
        jogador.cargo = obter_cargo_padrao_fase(nova_fase)
        jogador.moeda = request.form.get('moeda', jogador.moeda)
        db.session.commit()
        return redirect(url_for('dashboard'))

    return render_template('opcoes.html', jogador=jogador, aba_ativa='opcoes')

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True)