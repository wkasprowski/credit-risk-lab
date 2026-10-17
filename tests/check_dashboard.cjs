// Optional Node.js check: actual dashboard script with a minimal DOM shim,
// compared with independent SQL references. This does not test browser layout.
const fs=require('fs'),vm=require('vm'),assert=require('assert'),path=require('path');
const root=path.resolve(__dirname,'..');
const html=fs.readFileSync(path.join(root,'dashboard/index.html'),'utf8');
const script=html.match(/<script>([\s\S]+)<\/script>/)[1];
const elements={};let downloadedBlob=null,downloadName=null;
class Element{
 constructor(id){this.id=id;this.value='';this.textContent='';this.innerHTML='';this.options=[];this.listeners={};}
 add(option){this.options.push(option);if(!this.value)this.value=option.value;}
 addEventListener(type,fn){this.listeners[type]=fn;}
 click(){downloadName=this.download;}
}
for(const match of html.matchAll(/id="([^"]+)"/g))elements[match[1]]=new Element(match[1]);
for(const id of ['product','stage','scenario']){
 const match=html.match(new RegExp('id="'+id+'"><option value="([^"]+)"'));
 elements[id].value=match[1];
}
const document={getElementById:id=>elements[id],createElement:()=>new Element('link')};
const context={document,Intl,Set,Blob,console,
 Option:function(text,value){this.text=text;this.value=value;},
 URL:{createObjectURL(blob){downloadedBlob=blob;return 'blob:fixture';},revokeObjectURL(){}}
};
vm.createContext(context);vm.runInContext(script,context,{timeout:5000});
const cases=JSON.parse(fs.readFileSync(path.join(root,'outputs/dashboard_reference.json'),'utf8'));
for(const c of cases){
 for(const id of ['date','product','stage','scenario'])elements[id].value=c[id];
 elements.scenario.listeners.change();
 assert.strictEqual(elements['k-loans'].textContent,new Intl.NumberFormat('en-GB',{maximumFractionDigits:0}).format(c.count));
 assert.strictEqual(elements['k-ead'].textContent,(c.ead/1e6).toFixed(2)+'m PLN');
 assert.strictEqual(elements['k-ecl'].textContent,(c.ecl/1e6).toFixed(2)+'m PLN');
 const actual=[...elements['top-body'].innerHTML.matchAll(/<tr><td>(L-\d+)<\/td>/g)].map(m=>m[1]);
 assert.deepStrictEqual(actual,c.top);
 assert(!elements.trend.innerHTML.includes('NaN'));
 assert(!elements.calibration.innerHTML.includes('NaN'));
}
elements.export.onclick();
assert.strictEqual(downloadName,'credit_risk_top10.csv');
downloadedBlob.text().then(csv=>{
 assert.strictEqual(csv.split('\r\n').length,11);
 const result={method:'Node VM with minimal DOM shim; no browser layout test',
               independent_sql_filter_cases:cases.length,kpi_totals:'pass',top10_rankings:'pass',
               csv_export_contents:'pass'};
 fs.writeFileSync(path.join(root,'outputs/dashboard_checks.json'),JSON.stringify(result,null,2));
 console.log(JSON.stringify(result));
}).catch(e=>{console.error(e);process.exitCode=1});
