(() => {
  const $ = (id) => document.getElementById(id);

  const form = $("form");
  const url = $("url");
  const submit = $("submit");
  const status = $("status");
  const result = $("result");
  const pageTitle = $("pageTitle");
  const pageUrl = $("pageUrl");
  const pageMeta = $("pageMeta");
  const pageText = $("pageText");
  const imagesLabel = $("imagesLabel");
  const gallery = $("gallery");

  if (
    !form ||
    !url ||
    !submit ||
    !status ||
    !result ||
    !pageTitle ||
    !pageUrl ||
    !pageMeta ||
    !pageText ||
    !imagesLabel ||
    !gallery
  ) {
    console.error("Обнови страницу: Cmd+Shift+R");
    return;
  }

  // Всегда просим браузер; сервер сам отключит, если он недоступен
  const useBrowser = true;

  function showStatus(text, kind) {
    status.hidden = false;
    status.textContent = text;
    status.className = `status is-${kind}`;
  }

  function hideStatus() {
    status.hidden = true;
    status.textContent = "";
  }

  function escapeHtml(s) {
    return String(s)
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;")
      .replaceAll('"', "&quot;");
  }

  function normalizeUrl(raw) {
    let value = (raw || "").trim();
    if (!value) return "";
    if (!/^https?:\/\//i.test(value)) value = `https://${value}`;
    try {
      const u = new URL(value);
      if (u.protocol !== "http:" && u.protocol !== "https:") return "";
      return u.toString();
    } catch {
      return "";
    }
  }

  function showResult(data) {
    pageTitle.textContent = data.title || "Без названия";
    pageUrl.textContent = data.final_url || data.url || "";

    const words = data.word_count || 0;
    const how = data.render_used === "browser" ? "через браузер" : "быстрый режим";
    pageMeta.textContent = `${words} слов · ${how}`;

    const text = (data.content_text || "").trim() || (data.content_markdown || "").trim();
    if (text) {
      pageText.textContent = text;
      pageText.classList.remove("is-empty");
    } else {
      pageText.textContent =
        "Текст не нашёлся. Попробуй другую ссылку — лучше на статью, не на пустую страницу.";
      pageText.classList.add("is-empty");
    }

    const imgs = [];
    if (data.main_image) imgs.push(data.main_image);
    for (const src of data.images || []) {
      if (src && !imgs.includes(src)) imgs.push(src);
    }

    if (imgs.length) {
      imagesLabel.hidden = false;
      gallery.hidden = false;
      gallery.innerHTML = imgs
        .slice(0, 24)
        .map(
          (src) =>
            `<a href="${escapeHtml(src)}" target="_blank" rel="noopener noreferrer"><img src="${escapeHtml(src)}" alt="" loading="lazy" /></a>`
        )
        .join("");
    } else {
      imagesLabel.hidden = true;
      gallery.hidden = true;
      gallery.innerHTML = "";
    }

    result.hidden = false;
  }

  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    hideStatus();
    result.hidden = true;

    const pageUrlValue = normalizeUrl(url.value);
    if (!pageUrlValue) {
      showStatus("Вставь нормальную ссылку.\nНапример: https://www.aigerimkabaeva.com/", "error");
      url.focus();
      return;
    }
    url.value = pageUrlValue;

    submit.disabled = true;
    const oldLabel = submit.textContent;
    submit.textContent = "Секунду…";
    showStatus("Читаю страницу…", "info");

    try {
      const res = await fetch("/ui/parse", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          url: pageUrlValue,
          include_images: true,
          use_cache: false,
          use_browser: useBrowser,
        }),
      });

      let data = {};
      try {
        data = await res.json();
      } catch {
        showStatus("Сервер ответил непонятно. Обнови страницу и попробуй ещё раз.", "error");
        return;
      }

      if (!res.ok) {
        const err = data?.error;
        const msg = err?.message || `Ошибка ${res.status}`;
        showStatus(msg, "error");
        return;
      }

      hideStatus();
      showResult(data);
    } catch (err) {
      showStatus(
        "Не получилось связаться с сервисом.\nПроверь, что он запущен на http://127.0.0.1:8000/",
        "error"
      );
    } finally {
      submit.disabled = false;
      submit.textContent = oldLabel;
    }
  });
})();
