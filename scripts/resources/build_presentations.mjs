// Run from the repository root with @oai/artifact-tool, sharp, LibreOffice,
// pdftoppm, and a Python environment containing the site's requirements.
import { execFileSync } from 'node:child_process';
import fs from 'node:fs/promises';
import os from 'node:os';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { Presentation, PresentationFile } from '@oai/artifact-tool';
import sharp from 'sharp';

const root = process.cwd();
const publicDir = path.join(root, 'frontend/public');
const outputDir = path.resolve(process.argv[2] || path.join(publicDir, 'resources'));
const sans = 'Arial';
const serif = 'Georgia';
const width = 1280;
const height = 720;
const noLine = { fill: 'none', width: 0, style: 'solid' };
const themes = {
  light: { paper: '#F8F7F0', ink: '#183B2F', body: '#35493E', accent: '#80632B', line: '#B6BCAF', surface: '#E6EADF', chart: '#30664D' },
  dark:  { paper: '#101A16', ink: '#EDF0E6', body: '#C4D0C5', accent: '#DDC38A', line: '#536856', surface: '#263A2F', chart: '#8EB599' },
};

function createDeck(colors, name) {
  const deck = Presentation.create({ slideSize: { width, height } });
  deck.theme.defaultFont = sans;
  deck.theme.colorScheme = { name, themeColors: {
    bg1: colors.paper, bg2: colors.surface, tx1: colors.ink, tx2: colors.body,
    dk1: '#101A16', dk2: '#183B2F', lt1: '#F8F7F0', lt2: '#DDE6DA',
    accent1: colors.chart, accent2: colors.accent, accent3: '#779685',
    accent4: '#B1A466', accent5: '#8C7462', accent6: '#79A2A3',
    hlink: colors.chart, folHlink: colors.accent,
  }};
  return deck;
}
function page(deck, colors) {
  const slide = deck.slides.add();
  slide.background.fill = colors.paper;
  return slide;
}
function box(slide, name, fill, x, y, w, h) {
  return slide.shapes.add({name, geometry:'rect', position: {left:x,top:y,width:w,height:h}, fill, line:noLine});
}
function text(slide, name, value, x, y, w, h, size, color, options = {}) {
  const shape = slide.shapes.add({
    name, geometry:'textbox', position:{left:x,top:y,width:w,height:h}, fill:'none',line:noLine,
  });
  shape.text = value;
  shape.text.style = {
    typeface:sans, fontSize:size, color, insets:0, verticalAlignment:'middle',
    wrap:'square', autoFit:'none', ...options,
  };
  return shape;
}
function title(slide, colors, value) {
  return text(slide, 'Slide title', value, 70, 46, 1140, 105, 67, colors.ink, {typeface:serif});
}
function line(slide, colors, x, y, w) { return box(slide,'Divider',colors.line,x,y,w,2); }
async function image(slide, file, description, x,y,w,h) {
  const blob = await sharp(path.join(publicDir,'images/initiative',file)).resize({
    width:Math.round(w*1.7),height:Math.round(h*1.7),fit:'cover',position:'centre',
  }).jpeg({quality:85}).toBuffer();
  return slide.images.add({ blob, contentType:'image/jpeg', alt:description, fit:'cover', position:{left:x,top:y,width:w,height:h} });
}

async function introduction(c) {
  const p=createDeck(c,'Forest and gold');
  const cover=page(p,c);
  await image(cover,'compost-coaches.webp','Student Compost Coaches receive a plate at St. Andrew’s College.',593,0,687,720);
  text(cover,'School name','[School name]',62,52,480,48,26,c.accent,{bold:true});
  text(cover,'Presentation title','Golden\nPlate',56,133,516,250,102,c.ink,{typeface:serif});
  line(cover,c,62,487,451);
  text(cover,'Subject','How students can cut food\nwaste at lunch',62,515,487,111,32,c.body);
  cover.speakerNotes.text='Replace the school name and the bracketed details on the last slide. Introduce the student volunteers who will help at lunch. The photograph shows Compost Coaches at St. Andrew’s College, Aurora, Ontario. Source: https://goldenplate.ca/how-it-works';

  const routine=page(p,c);
  title(routine,c,'What Happens at Lunch?');
  const steps=[
    ['In the lunch line','Choose a portion that suits your appetite.'],
    ['At the dish return','Show your plate to a student volunteer before you scrape it.'],
    ['After lunch','The volunteers share how many clean plates our school recorded.'],
  ];
  steps.forEach(([label, instruction],index) => {
    const y=182+index*151;
    line(routine,c,72,y,1136);
    text(routine,label,label,72,y+18,342,76,32,c.ink,{bold:true});
    text(routine,'Instruction',instruction,436,y+14,765,88,32,c.body);
  });
  routine.speakerNotes.text='Explain how portions work in your dining hall. Students can stop when they feel full. At the dish return, ask students to let the coach see each plate before scraping or stacking it.';

  const story=page(p,c);
  await image(story,'golden-plate-winner.webp','A Golden Plate winner beside his menu selection at the serving station.',58,108,510,458);
  text(story,'Photo caption','A winner and his menu choice at St. Andrew’s.',58,578,510,52,19,c.body);
  text(story,'School','St. Andrew’s College',636,71,580,48,26,c.accent,{bold:true});
  text(story,'Example title','Who Picked\nFriday’s Lunch?',630,135,585,193,68,c.ink,{typeface:serif});
  text(story,'Example','At St. Andrew’s, a clean plate earns an entry in the school’s award draw. Winners can suggest a dish for the cafeteria.',636,342,550,160,31,c.body);
  line(story,c,636,551,538);
  text(story,'Winning menu','One Friday, the winners chose grilled cheese.',636,567,548,88,27,c.ink,{bold:true});
  story.speakerNotes.text='Ask the audience what dish they would choose. Your school can agree on its own recognition. School source: https://goldenplate.ca/stories. Original reel: https://www.instagram.com/reel/DBgb3-MRESr/';

  const launch=page(p,c);
  title(launch,c,'Our First Lunch');
  [
    ['When','[Day and lunch period]'],['Where','[Dish-return location]'],
    ['Our school’s reward','[Recognition or reward]'],['Want to volunteer?','Talk to [student or staff lead].'],
  ].forEach(([label,value],index) => {
    const y=170+index*115;
    line(launch,c,72,y,1136);
    text(launch,label,label,72,y+14,366,64,29,c.accent,{bold:true});
    text(launch,'Editable detail',value,465,y+10,732,75,37,c.ink);
  });
  launch.speakerNotes.text='Add the lunch date, lunch period, dish-return location and contact person. If you are tracking a shared goal without a prize, replace the reward row with your goal. Invite students to help record or share the results.';
  return p;
}

function generalTemplate(c) {
  const p=createDeck(c,'Forest and gold');
  const cover=page(p,c);
  text(cover,'Presenter','[Presenter or team]',80,72,1100,54,26,c.accent,{bold:true});
  text(cover,'Title','Presentation Title',73,190,1140,151,99,c.ink,{typeface:serif});
  line(cover,c,80,440,1100);
  text(cover,'Subject','[Topic or occasion]',80,476,830,67,33,c.body);
  text(cover,'Date','[Date]',940,476,240,67,27,c.body,{alignment:'right'});
  cover.speakerNotes.text='Replace the title, presenter, occasion and date. Duplicate, reorder or delete any of the following layouts. All text and shapes are editable.';

  const agenda=page(p,c);
  title(agenda,c,'Agenda');
  ['[Opening topic]','[Main discussion]','[Decision or next step]'].forEach((topic,idx)=>{
    const y=197+idx*127;
    line(agenda,c,72,y,1136);
    text(agenda,'Item number',String(idx+1).padStart(2,'0'),73,y+14,100,76,42,c.accent,{typeface:serif});
    text(agenda,'Agenda topic',topic,206,y+14,938,76,39,c.ink);
  });
  agenda.speakerNotes.text='Replace the three topics. To add another, copy an entire row and adjust the spacing.';

  const idea=page(p,c);
  title(idea,c,'[Key Idea]');
  line(idea,c,72,169,1136);
  text(idea,'Main point','[One sentence that explains the main point.]',70,226,555,297,53,c.ink,{typeface:serif});
  text(idea,'Evidence heading','Supporting Evidence',706,244,478,59,29,c.accent,{bold:true});
  text(idea,'Supporting detail','[Add the observation, example or source that supports this point.]',706,322,468,205,34,c.body);
  idea.speakerNotes.text='Use the left side for one clear idea. Provide enough evidence on the right for the audience to judge it.';

  const visual=page(p,c);
  title(visual,c,'[Image Title]');
  // A native picture placeholder survives slide duplication and imports as an editable area.
  const layout=p.layouts.add('Image and Caption');
  layout.placeholders.add({type:'picture',index:1,geometry:'rect',position:{left:72,top:193,width:697,height:426},fill:c.surface,line:{style:'solid',width:1,fill:c.line}});
  visual.setLayout(layout);
  const placeholder=visual.placeholders.getItem('picture');
  placeholder.name='Insert photograph';
  box(visual,'Picture mat',c.surface,72,193,697,426);
  // Keep the native insertion target above its background.
  placeholder.bringToFront?.();
  text(visual,'Image caption','[What the audience should notice]',821,231,375,200,44,c.ink,{typeface:serif});
  text(visual,'Source or credit','[Source or credit]',825,498,373,70,23,c.body);
  visual.speakerNotes.text='Use the picture placeholder to insert a photograph or illustration. You can also drag or paste an image over the shaded rectangle. Add a descriptive caption and credit.';

  const results=page(p,c);
  title(results,c,'[Results Over Time]');
  text(results,'Metric and units','[Metric and unit]',73,153,1100,47,26,c.body);
  const axisText={typeface:sans,fontSize:20,color:c.body};
  results.charts.add('bar',{
    position:{left:74,top:219,width:1093,height:364},categories:['Period 1','Period 2','Period 3','Period 4'],
    series:[{name:'Example values',values:[24,39,35,53],fill:c.chart}],hasLegend:false,
    barOptions:{direction:'column',grouping:'clustered',gapWidth:88},
    titlePlacement:'none',chartFill:c.paper,chartLine:noLine,plotAreaFill:c.paper,plotAreaLine:noLine,
    xAxis:{textStyle:axisText,line:{style:'solid',fill:c.line,width:1}},
    yAxis:{min:0,majorUnit:10,textStyle:axisText,majorGridlines:{style:'solid',fill:c.line,width:1}},
  });
  text(results,'Data source','Sample values. Replace with your data and source.',75,614,1110,50,24,c.body);
  results.speakerNotes.text='Select the chart and choose Edit Data to change periods, units and values. Replace the sample source note.';

  const schedule=page(p,c);
  title(schedule,c,'Project Schedule');
  const values=[['Stage','Owner','Target date'],['[Preparation]','[Owner]','[Date]'],['[Delivery]','[Owner]','[Date]'],['[Review]','[Owner]','[Date]']];
  const table=schedule.tables.add({rows:4,columns:3,left:72,top:192,width:1136,height:343,columnWidths:[490,357,289],values});
  table.styleOptions={headerRow:false,bandedRows:false};
  table.borders.assign({style:'solid',fill:c.line,width:1});
  for(let row=0;row<values.length;row++) {
    table.rows[row].height=row===0?67:92;
    for(let col=0;col<3;col++) {
      const cell=table.getCell(row,col);
      cell.fill=row===0?c.surface:c.paper;
      cell.text.style={typeface:sans,fontSize:row===0?25:29,bold:row===0,color:row===0?c.accent:c.ink,verticalAlignment:'middle'};
    }
  }
  schedule.speakerNotes.text='Edit the stage names, owners and dates. Insert or remove rows in the native table.';

  const close=page(p,c);
  title(close,c,'Next Steps');
  line(close,c,72,172,1136);
  text(close,'Next action','[The next action]',71,223,1140,151,75,c.ink,{typeface:serif});
  text(close,'Who and when','[Owner] will [action] by [date].',75,397,1128,92,39,c.body);
  text(close,'Contact','[Name and contact details]',76,601,1124,53,25,c.accent);
  close.speakerNotes.text='Identify who will take the next action and by when. Add a contact if the audience needs to follow up.';
  return p;
}

const staging = await fs.mkdtemp(path.join(os.tmpdir(), 'golden-plate-slides-'));
try {
  for (const [mode, colors] of Object.entries(themes)) {
    const intro = await introduction(colors);
    const stem = mode === 'light' ? 'golden-plate-assembly' : 'golden-plate-assembly-dark';
    await (await PresentationFile.exportPptx(intro)).save(path.join(staging, stem + '.pptx'));
    const general = generalTemplate(colors);
    await (await PresentationFile.exportPptx(general)).save(path.join(staging, 'presentation-template-' + mode + '.pptx'));
  }
  const packager = fileURLToPath(new URL('./package_presentations.py', import.meta.url));
  execFileSync(process.env.PYTHON || 'python3', [packager, staging, outputDir], { stdio: 'inherit' });
} finally {
  await fs.rm(staging, { recursive: true, force: true });
}
