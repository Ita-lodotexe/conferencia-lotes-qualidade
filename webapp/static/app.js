const CATEGORIAS = [
  { chave: "Válido", cor: "var(--valido)", corHex: "#2f9e64" },
  { chave: "Divergência", cor: "var(--divergencia)", corHex: "#a50034" },
  { chave: "Ambíguo", cor: "var(--ambiguo)", corHex: "#e0954b" },
  { chave: "Erro de Entrada", cor: "var(--erro)", corHex: "#6b6470" },
];

const form = document.getElementById("upload-form");
const inputArquivo = document.getElementById("arquivo");
const dropzone = document.getElementById("dropzone");
const dropzoneTexto = document.getElementById("dropzone-texto");
const btnEnviar = document.getElementById("btn-enviar");
const mensagemErro = document.getElementById("mensagem-erro");
const mensagemCarregando = document.getElementById("mensagem-carregando");
const resultadoSection = document.getElementById("resultado-section");
const metricasEl = document.getElementById("metricas");
const donutEl = document.getElementById("donut");
const legendaEl = document.getElementById("legenda");
const evolucaoEl = document.getElementById("evolucao");
const btnDownload = document.getElementById("btn-download");
const btnLog = document.getElementById("btn-log");
const logTexto = document.getElementById("log-texto");

let dashboardIdAtual = null;

function escapeHtml(valor) {
  const div = document.createElement("div");
  div.textContent = valor === null || valor === undefined ? "" : String(valor);
  return div.innerHTML;
}

function mostrarErro(texto) {
  mensagemErro.textContent = texto;
  mensagemErro.hidden = false;
}

function limparErro() {
  mensagemErro.hidden = true;
  mensagemErro.textContent = "";
}

inputArquivo.addEventListener("change", () => {
  const arquivo = inputArquivo.files[0];
  dropzoneTexto.textContent = arquivo ? arquivo.name : "Clique para escolher o arquivo ou arraste aqui";
  btnEnviar.disabled = !arquivo;
});

["dragover", "dragleave", "drop"].forEach((evento) => {
  dropzone.addEventListener(evento, (e) => {
    e.preventDefault();
    dropzone.classList.toggle("dropzone--active", evento === "dragover");
  });
});

dropzone.addEventListener("drop", (e) => {
  const arquivo = e.dataTransfer.files[0];
  if (arquivo) {
    inputArquivo.files = e.dataTransfer.files;
    dropzoneTexto.textContent = arquivo.name;
    btnEnviar.disabled = false;
  }
});

function renderMetricas(porClassificacao, percentual, total) {
  metricasEl.innerHTML = CATEGORIAS.map((categoria) => {
    const valor = porClassificacao[categoria.chave] || 0;
    const pct = percentual[categoria.chave] || 0;
    return `
      <div class="metrica">
        <strong style="color:${categoria.corHex}">${escapeHtml(valor)}</strong>
        <span>${escapeHtml(categoria.chave)}</span>
        <small>${escapeHtml(pct)}%</small>
      </div>`;
  }).join("");

  legendaEl.innerHTML = CATEGORIAS.map(
    (categoria) => `
      <li>
        <span class="ponto" style="background:${categoria.corHex}"></span>
        ${escapeHtml(categoria.chave)}
      </li>`
  ).join("");
}

function renderDonut(porClassificacao, total) {
  donutEl.setAttribute("data-total", total);

  if (!total) {
    donutEl.style.background = "var(--lg-rose-softer)";
    return;
  }

  let acumulado = 0;
  const fatias = CATEGORIAS.map((categoria) => {
    const valor = porClassificacao[categoria.chave] || 0;
    const inicio = (acumulado / total) * 360;
    acumulado += valor;
    const fim = (acumulado / total) * 360;
    return `${categoria.corHex} ${inicio}deg ${fim}deg`;
  }).join(", ");

  donutEl.style.background = `conic-gradient(${fatias})`;
}

function renderEvolucao(evolucaoPorDia) {
  if (!evolucaoPorDia.length) {
    evolucaoEl.innerHTML = "";
    return;
  }

  const maiorTotal = Math.max(...evolucaoPorDia.map((d) => d.total), 1);

  evolucaoEl.innerHTML = evolucaoPorDia
    .map((dia) => {
      const problemas = (dia["Divergência"] || 0) + (dia["Ambíguo"] || 0);
      const alturaTotal = Math.round((dia.total / maiorTotal) * 100);
      const alturaProblemas = Math.round((problemas / maiorTotal) * 100);
      const rotulo = (dia.dia || "").replace(/^Insp_/, "").replace(/_/g, "/");
      return `
        <div class="evolucao-dia">
          <div class="evolucao-barras" title="${escapeHtml(dia.dia)}: total ${dia.total}, problemas ${problemas}">
            <div class="evolucao-barra-total" style="height:${alturaTotal}%"></div>
            <div class="evolucao-barra-problema" style="height:${alturaProblemas}%"></div>
          </div>
          <span>${escapeHtml(rotulo)}</span>
        </div>`;
    })
    .join("");
}

form.addEventListener("submit", async (e) => {
  e.preventDefault();
  limparErro();

  const arquivo = inputArquivo.files[0];
  if (!arquivo) {
    return;
  }

  const dadosFormulario = new FormData();
  dadosFormulario.append("arquivo", arquivo);

  btnEnviar.disabled = true;
  mensagemCarregando.hidden = false;
  resultadoSection.hidden = true;
  logTexto.hidden = true;

  try {
    const resposta = await fetch("/api/aula22/dashboard", {
      method: "POST",
      body: dadosFormulario,
    });

    const dados = await resposta.json();

    if (!resposta.ok) {
      throw new Error(dados.detail || "Não foi possível processar a planilha.");
    }

    dashboardIdAtual = dados.id;
    renderMetricas(dados.por_classificacao, dados.percentual, dados.total);
    renderDonut(dados.por_classificacao, dados.total);
    renderEvolucao(dados.evolucao_por_dia);
    resultadoSection.hidden = false;
  } catch (erro) {
    mostrarErro(erro.message);
  } finally {
    mensagemCarregando.hidden = true;
    btnEnviar.disabled = false;
  }
});

btnDownload.addEventListener("click", () => {
  if (!dashboardIdAtual) {
    return;
  }
  window.location.href = `/api/aula22/dashboard/${dashboardIdAtual}/download`;
});

btnLog.addEventListener("click", async () => {
  if (!dashboardIdAtual) {
    return;
  }
  const resposta = await fetch(`/api/aula22/dashboard/${dashboardIdAtual}/log`);
  const texto = await resposta.text();
  logTexto.textContent = texto;
  logTexto.hidden = false;
});
