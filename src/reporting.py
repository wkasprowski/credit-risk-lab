"""Reports use measured pipeline results, not invented performance numbers."""
import json
from pathlib import Path
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from reportlab.pdfgen import canvas
from reportlab.lib.colors import HexColor
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.utils import ImageReader
from reportlab.platypus import Paragraph
from reportlab.lib.styles import ParagraphStyle

LABELS = {"cash_loan":"Cash loan","secured_loan":"Secured loan","credit_card":"Credit card"}
NAVY, TEAL, ORANGE = "#11243b", "#147d75", "#dc8046"


def charts(output, fact, latest):
    plt.rcParams.update({"font.family":"DejaVu Sans","font.size":10,
                         "axes.spines.top":False,"axes.spines.right":False,
                         "axes.titleweight":"bold","figure.facecolor":"white"})
    destination = output / "charts"
    destination.mkdir(exist_ok=True)
    bins = pd.read_csv(output / "pd_calibration_bins.csv")
    fig,ax = plt.subplots(figsize=(6.8,3.5),layout="constrained")
    ax.plot([0,bins.mean_pd.max()*1.2],[0,bins.mean_pd.max()*1.2],"--",color="#c0c8d0",label="Kalibracja idealna")
    ax.errorbar(bins.mean_pd,bins.observed_rate,
                yerr=np.array([bins.observed_rate-bins.wilson_low,bins.wilson_high-bins.observed_rate]),
                fmt="o-",color=TEAL,capsize=3,label="Test OOT, przedziały Wilsona 95%")
    ax.set(xlabel="Średnia prognozowana PD",ylabel="Odsetek niewypłacalności",title="PD: prognoza a obserwacja")
    ax.legend(fontsize=8,loc="upper left")
    fig.savefig(destination / "pd_calibration.png",dpi=180)
    plt.close(fig)
    group = latest.groupby("stage")["ecl_weighted"].sum()
    fig,ax = plt.subplots(figsize=(6.8,3.5),layout="constrained")
    bars = ax.bar([f"Stage {s}" for s in group.index],group.values/1e6,color=[TEAL,ORANGE,NAVY])
    ax.bar_label(bars,fmt="%.2f mln",padding=4)
    ax.set(ylabel="ECL [mln PLN]",title="Odpis według etapu ryzyka",ylim=(0,max(group.values)/1e6*1.25))
    fig.savefig(destination / "stage_ecl.png",dpi=180)
    plt.close(fig)
    monthly = fact.groupby("report_date")[["ecl_base","ecl_adverse","ecl_weighted"]].sum()/1e6
    fig,ax = plt.subplots(figsize=(8.0,3.5),layout="constrained")
    for column,color,label in [("ecl_base",TEAL,"Bazowy"),("ecl_adverse",ORANGE,"Niekorzystny"),("ecl_weighted",NAVY,"Ważony")]:
        ax.plot(monthly.index.str[:7],monthly[column],color=color,label=label,marker=".")
    ax.set(ylabel="ECL [mln PLN]",title="Wrażliwość portfela na scenariusz")
    ax.tick_params(axis="x",rotation=35,labelsize=8)
    ax.legend(fontsize=9)
    fig.savefig(destination / "ecl_trend.png",dpi=180)
    plt.close(fig)


def dashboard(root, fact, summary):
    data = fact.copy()
    data["pd_exposure"] = np.where(data.stage<3,data.pd_12m*data.ead,0)
    data["performing_ead"] = np.where(data.stage<3,data.ead,0)
    agg = data.groupby(["report_date","product","stage"],as_index=False).agg(
        loans=("loan_id","size"),ead=("ead","sum"),balance=("balance","sum"),
        pd_exposure=("pd_exposure","sum"),performing_ead=("performing_ead","sum"),
        ecl_weighted=("ecl_weighted","sum"),ecl_base=("ecl_base","sum"),
        ecl_optimistic=("ecl_optimistic","sum"),ecl_adverse=("ecl_adverse","sum"))
    # Union of per-scenario, per-product, per-stage top 12 contains every
    # possible top ten shown by the available filters.
    choices = []
    for scenario in ["weighted","base","adverse","optimistic"]:
        choices.append(fact.sort_values(f"ecl_{scenario}",ascending=False)
                       .groupby(["report_date","product","stage"]).head(12))
    cols = ["loan_id","report_date","product","stage","dpd","pd_12m","lgd","ead",
            "ecl_weighted","ecl_base","ecl_optimistic","ecl_adverse","stage_reason"]
    top = pd.concat(choices).drop_duplicates(["loan_id","report_date"])[cols]
    enriched = dict(summary)
    enriched["calibration_bins"] = json.loads(pd.read_csv(root / "outputs" / "pd_calibration_bins.csv").to_json(orient="records"))
    payload = {"aggregates":json.loads(agg.to_json(orient="records")),
               "top":json.loads(top.to_json(orient="records")),"metrics":enriched,"labels":LABELS}
    html = (root / "dashboard" / "template.html").read_text(encoding="utf-8")
    html = html.replace("__PAYLOAD__",json.dumps(payload,ensure_ascii=False,separators=(",",":")).replace("</","<\\/"))
    (root / "dashboard" / "index.html").write_text(html,encoding="utf-8")


def register_fonts():
    candidates = [
        (Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),Path("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf")),
        (Path("C:/Windows/Fonts/arial.ttf"),Path("C:/Windows/Fonts/arialbd.ttf")),
        (Path("/Library/Fonts/Arial.ttf"),Path("/Library/Fonts/Arial Bold.ttf")),
    ]
    for normal,bold in candidates:
        if normal.exists() and bold.exists():
            pdfmetrics.registerFont(TTFont("CRNormal",str(normal)))
            pdfmetrics.registerFont(TTFont("CRBold",str(bold)))
            pdfmetrics.registerFontFamily("CRNormal",normal="CRNormal",bold="CRBold",italic="CRNormal",boldItalic="CRBold")
            return
    raise RuntimeError("PDF requires Arial or DejaVu Sans with Polish characters. HTML report is already generated.")


def pdf_report(output, latest, summary):
    register_fonts()
    path = output / "recruiter_brief.pdf"
    c = canvas.Canvas(str(path),pagesize=(595.28,841.89))
    c.setTitle("Credit Risk Lab - projekt portfolio do analizy ryzyka kredytowego")
    c.setAuthor("Credit Risk Lab contributors")
    c.setSubject("Dane syntetyczne; edukacyjne przybliżenie mechanizmu MSSF 9")
    totals,pdm,lgdm = summary["totals"],summary["pd"]["full_calibrated"],summary["lgd"]
    def text(x,y,t,size=10,color=NAVY,bold=False):
        c.setFillColor(HexColor(color));c.setFont("CRBold" if bold else "CRNormal",size);c.drawString(x,y,t)
    def para(t,x,y,width=499,size=10,color=NAVY,leading=15):
        p = Paragraph(t,ParagraphStyle("body",fontName="CRNormal",fontSize=size,leading=leading,textColor=HexColor(color)))
        _,height = p.wrap(width,500)
        p.drawOn(c,x,y-height)
        return y-height
    def footer(page):
        c.setStrokeColor(HexColor("#dfe6eb"));c.line(48,44,547,44)
        text(48,29,"Synthetic data | educational portfolio",7,"#627589")
        text(526,29,f"{page}/2",7,"#627589")
    def card(x,y,w,label,value):
        c.setFillColor(HexColor("#eef5f5"));c.roundRect(x,y,w,65,8,fill=1,stroke=0)
        text(x+13,y+43,label,8,"#59727c")
        text(x+13,y+15,value,20,TEAL,True)
    c.setFillColor(HexColor(NAVY));c.rect(0,698,596,144,fill=1,stroke=0)
    text(48,792,"CREDIT RISK LAB",11,"#7fd1c5",True)
    text(48,757,"Od danych do odpisu",27,"#ffffff",True)
    text(48,727,"SQL  /  Python  /  PD  /  LGD  /  scenariusze ECL",10,"#dfe6ef")
    text(48,675,"Educational credit risk portfolio",10,NAVY,True)
    text(48,657,f"Portfel detaliczny PLN | data raportowa: {totals['report_date']}",9,"#627589")
    card(48,568,157,"KONTRAKTY",f"{totals['portfolio_loans']:,}".replace(","," "))
    card(219,568,157,"EKSPOZYCJA EAD",f"{totals['ead_pln']/1e6:.1f} mln zł")
    card(390,568,157,"ODPIS WAŻONY ECL",f"{totals['ecl_weighted_pln']/1e6:.2f} mln zł")
    y = para("<b>Problem biznesowy.</b> Jak oszacować oczekiwaną stratę, wskazać portfele wymagające uwagi i wyjaśnić różnicę między wynikiem bazowym a niekorzystnym?",48,544)
    stress = totals["ecl_adverse_pln"]/totals["ecl_base_pln"]-1
    stage = latest.groupby("stage").ecl_weighted.sum()
    share3 = stage.get(3,0)/totals["ecl_weighted_pln"]
    y = para(f"<b>Wynik symulacji.</b> Pokrycie EAD odpisem wynosi {totals['coverage_ratio']:.2%}. Scenariusz niekorzystny podnosi ECL o {stress:.1%} względem bazowego przy stałej klasyfikacji etapów. Stage 3 odpowiada za {share3:.1%} odpisu ważonego.",48,y-13)
    c.drawImage(ImageReader(str(output / "charts" / "stage_ecl.png")),103,246,width=389,height=200,mask="auto")
    text(48,225,"Co demonstruje projekt",13,NAVY,True)
    y = para("<b>SQL:</b> łączenie źródeł, deduplikacja ROW_NUMBER, funkcje okna i uzgodnienie sum.<br/><b>Python:</b> regresja logistyczna PD, kalibracja na osobnym okresie, model LGD z odzysków.<br/><b>Ryzyko:</b> Stage 1/2/3, PD marginalne, harmonogram EAD, dyskonto i wagi scenariuszy.<br/><b>Raportowanie:</b> interaktywny HTML offline oraz pliki CSV, Power Query M i miary DAX.",48,207,size=9.5,leading=15)
    para("<b>Zakres:</b> demonstrator edukacyjny. Wyniki opisują wyłącznie wygenerowane dane; projekt nie odtwarza modeli, polityki ani danych rzeczywistej instytucji. Raport Power BI wymaga złożenia w Desktop według dołączonej instrukcji.",48,y-12,size=8.5,color="#627589",leading=12)
    footer(1);c.showPage()
    text(48,790,"Walidacja, którą można odtworzyć",23,NAVY,True)
    text(48,768,"Kontrole jakości i jawne ograniczenia",10,"#627589")
    card(48,678,157,"ROC-AUC / GINI",f"{pdm['roc_auc']:.3f} / {pdm['gini']:.3f}")
    card(219,678,157,"BRIER SCORE",f"{pdm['brier']:.4f}")
    card(390,678,157,"LGD: BŁĄD MAE",f"{lgdm['mae']:.3f}")
    ci = summary["pd"]["auc_bootstrap_95ci"]
    para(f"Test PD: {pdm['rows']:,} niezależnych obserwacji z 2024 r.; wyniki znane po 12 miesiącach. AUC: przedział bootstrap 95% [{ci[0]:.3f}; {ci[1]:.3f}]. Trening: 2018-2020, kalibracja: 2022. Okna wyników poprzedniego zbioru kończą się przed pierwszą obserwacją następnego.",48,659,size=9,leading=13)
    c.drawImage(ImageReader(str(output / "charts" / "pd_calibration.png")),91,390,width=412,height=212,mask="auto")
    text(48,365,"Kontrole danych i ślad obliczeń",12,NAVY,True)
    dq = summary["data_quality"]
    y = para(f"Deduplikacja usuwa {dq['duplicates_removed']} kopii; {dq['quarantined_rows']} błędne rekordy trafiają do kwarantanny. Brakujące dochody są uzupełniane medianą wyznaczoną wyłącznie na treningu. Uzgodniono kwoty SQL z Pythonem oraz składniki miesięczne dla {summary['reconciliation']['audit_loans']} kontraktów.",48,348,size=9,leading=13)
    text(48,y-22,"Najważniejsze ograniczenia",12,NAVY,True)
    y = para("Stała miesięczna intensywność defaultu; założone mnożniki scenariuszy i CCF; uproszczony czas życia kart; stała klasyfikacja etapów między scenariuszami; LGD z zakończonych przypadków bez korekty biasu otwartych windykacji. Stage 3 używa proxy LGD zamiast indywidualnej prognozy odzysków. Progi SICR są założeniami projektu. Brier łączy ocenę prawdopodobieństw i dyskryminacji; krzywa pokazuje kalibrację.",48,y-32,size=8.8,leading=12.5)
    text(48,y-23,"Demonstracja w 3 minuty",12,NAVY,True)
    y = para("1. Otwórz dashboard/index.html; zmień scenariusz i produkt.<br/>2. Pokaż rekord w kwarantannie oraz SQL z funkcją okna.<br/>3. Otwórz ecl_calculation_audit.csv i wyjaśnij wkład miesięcznej PD do odpisu.<br/>4. Wskaż ograniczenie modelu oraz następną zmianę do przetestowania.",48,y-34,size=9,leading=13)
    text(48,94,"Źródła metodologii i narzędzi",8,NAVY,True)
    for yy,label,url in [(79,"BIS: IFRS 9 and expected loss provisioning","https://www.bis.org/fsi/fsisummaries/ifrs9.pdf"),
                         (66,"scikit-learn: probability calibration","https://scikit-learn.org/stable/modules/calibration.html"),
                         (53,"Microsoft Learn: data sources in Power BI Desktop","https://learn.microsoft.com/en-us/power-bi/connect-data/desktop-data-sources")]:
        text(48,yy,label,7,TEAL)
        c.linkURL(url,(48,yy-2,450,yy+8),relative=0,thickness=0)
    footer(2);c.save()


def create_reports(root, fact, latest, summary):
    output = root / "outputs"
    charts(output,fact,latest)
    dashboard(root,fact,summary)
    pdf_report(output,latest,summary)
