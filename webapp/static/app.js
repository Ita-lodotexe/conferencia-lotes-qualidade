const form = document.getElementById("upload-form");
const inputArquivo = document.getElementById("arquivo");
const dropzone = document.getElementById("dropzone");
const dropzoneTexto = document.getElementById("dropzone-texto");
const btnEnviar = document.getElementById("btn-enviar");
const mensagemErro = document.getElementById("mensagem-erro");
const mensagemCarregando = document.getElementById("mensagem-carregando");
const resultadoSection = document.getElementById("resultado-section");
const metricasEl = document.getElementById("metricas");
const tabelaCorpo = document.querySelector("#tabela-divergencias tbody");
const semDivergencias = document.getElementById("sem-divergencias");
const btnDownload = document.getElementById("btn-download");

let relatorioIdAtual = null;

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

function renderMetricas(resumo) {
  const itens = [
    { label: "Total de lotes", valor: resumo.total_lotes },
    { label: "Lotes conformes", valor: resumo.lotes_conformes, ok: true },
    { label: "Lotes com divergência", valor: resumo.lotes_com_divergencia },
    { label: "Total de divergências", valor: resumo.total_divergencias },
  ];

  metricasEl.innerHTML = itens
    .map(
      (item) => `
      <div class="metrica${item.ok ? " metrica--ok" : ""}">
        <strong>${escapeHtml(item.valor)}</strong>
        <span>${escapeHtml(item.label)}</span>
      </div>`
    )
    .join("");
}

function renderDivergencias(divergencias) {
  tabelaCorpo.innerHTML = "";

  if (!divergencias.length) {
    semDivergencias.hidden = false;
    return;
  }
  semDivergencias.hidden = true;

  divergencias.forEach((d) => {
    const linha = document.createElement("tr");
    linha.innerHTML = `
      <td>${escapeHtml(d.regra)}</td>
      <td>${escapeHtml(d.lote_id ?? "—")}</td>
      <td>${escapeHtml(d.linha ?? "—")}</td>
      <td>${escapeHtml(d.descricao)}</td>
    `;
    tabelaCorpo.appendChild(linha);
  });
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

  try {
    const resposta = await fetch("/api/relatorios", {
      method: "POST",
      body: dadosFormulario,
    });

    const dados = await resposta.json();

    if (!resposta.ok) {
      throw new Error(dados.detail || "Não foi possível gerar o relatório.");
    }

    relatorioIdAtual = dados.id;
    renderMetricas(dados.resumo);
    renderDivergencias(dados.divergencias);
    resultadoSection.hidden = false;
  } catch (erro) {
    mostrarErro(erro.message);
  } finally {
    mensagemCarregando.hidden = true;
    btnEnviar.disabled = false;
  }
});

btnDownload.addEventListener("click", () => {
  if (!relatorioIdAtual) {
    return;
  }
  window.location.href = `/api/relatorios/${relatorioIdAtual}/download`;
});
