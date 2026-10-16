# Map boundary reference review

Reviewed on 2026-10-15. This is a visual comparison of map content, not an
assessment of requirements for operating a service in mainland China.

## Latest user clarification

The user subsequently clarified: "i just want to be correct and represent the
real situation. it doesnthave to be government approved."
Government approval is therefore **not an acceptance prerequisite** for provider
selection. The approval evidence below is background, not a reason by itself to
reject Mapbox. Prior supplied maps remain comparison references, but a provider's
worldview must not be described as proving all territorial claims or actual
administrative control. Accurate geography, useful imagery and an intelligible
presentation of boundaries are the current priorities. No provider migration
has been performed as part of this clarification.

## User's reference

- File: `/Users/antineutrino/Downloads/横版原图下载.jpeg`
- Image dimensions: 10336 × 7257.
- Title: 中国地图对开横版.
- Printed review number: GS(2021)5448号. This identifies the supplied image;
  it is not approval for the website or for Mapbox's map.
- Reference details include Taiwan Province, Diaoyu Dao and Chiwei Yu,
  the eastern Himalayan boundary, Aksai Chin and the western boundary,
  and the South China Sea island groups and segmented maritime markings.

## Mapbox preview inspected

Official demo: <https://docs.mapbox.com/mapbox-gl-js/toggle-worldviews-demo.html>

The **China (CN)** control was visibly selected throughout the inspection.
The demo uses Mapbox Standard. Its default label language was not changed;
the displayed labels mix Chinese and local-language names.

| Area | Observations | Result |
| --- | --- | --- |
| Taiwan and nearby waters | Taiwan is visible and segmented markings appear east and south of it. The visible label is 台湾; the reference spells out 台湾省. | Major markings present; exact boundary and labeling match not established. |
| 藏南 / eastern Himalayas | The displayed territorial outline follows the southern edge of the area around Tawang, Itanagar and Pasighat, broadly corresponding to the reference's depiction. | Broad visual correspondence only. |
| Aksai Chin / western boundary | Inspected the outline around Ladakh, Hotan and Rutog against the western part of the reference. | Inspected visually; exact geometry not established. |
| South China Sea | Segmented markings are visible around the sea, including west of the Philippines and north of Borneo. | Major markings present. Individual reef/island names and every segment position remain unverified. |
| Diaoyu Dao / Chiwei Yu and small offshore features | The reference clearly includes these. The preview inspection did not establish a detailed match. | Unverified. |

**Overall status: not approved as an exact match to the user's reference.**
Selecting CN is necessary for the requested Mapbox depiction but is not, by
itself, evidence that every feature in this particular reference matches.
The reference JPEG supplies a visual target, not georeferenced boundary vectors.
No boundary geometry was traced, invented, or added to the application.
At the time of this initial inspection the website still used its existing
Esri/OpenFreeMap combination. See the integration status below for the
subsequent user-authorized switch to Mapbox.

## Acceptance requirements for a future integration

The user supplied these legal references after the visual review. Both original
NPC pages were retrieved and their full text read on 2026-10-15:

- [中华人民共和国测绘法, revised 2017](http://www.npc.gov.cn/zgrdw/npc/xinwen/2017-04/27/content_2020927.htm):
  Article 20 identifies the State Council-approved national-boundary standard
  drawing; Article 21 addresses standard administrative-boundary drawings.
  Article 38 requires adherence to map compilation, content-representation and
  review provisions and addresses approved maps and checking new map content.
- [地图管理条例, State Council Order 664](http://www.npc.gov.cn/zgrdw/npc/lfzt/rlyw/2016-10/27/content_1999914.htm):
  Article 9 addresses complete territorial representation in relevant national
  and world maps; Article 10 prescribes the reference drawings for national and
  international boundaries; Article 11 addresses administrative boundaries.
  Article 22 addresses prominently displaying the applicable review number.

These are legal requirements and references to official drawings, not downloadable
boundary-coordinate datasets or confirmation that a particular Mapbox style
matches them. A visual comparison alone cannot establish statutory approval.
For detailed map-content checks, also consult the Ministry of Natural Resources'
[2023 公开地图内容表示规范](https://www.mfa.gov.cn/web/wjb_673085/zzjg_673183/bjhysws_674671/bhflfg/dtdmxgfl/202303/P020230313585504979937.pdf).

The requested implementation scope remains **map boundaries, territories and
names**, following the user's correction. Do not infer authorization to migrate
hosting or undertake mainland-China business licensing/registration.

## Detailed requirements from the supplied 2023 PDF

The user subsequently supplied
`/Users/antineutrino/Downloads/f91670f2-8b91-4f44-a5a2-3aecd60a4c41.pdf`.
All five pages were extracted and rendered for inspection; pages 1–4 contain
the text and page 5 is blank. The title is **公开地图内容表示规范**,
自然资规〔2023〕2号, issued by the Ministry of Natural Resources on 2023-02-06.
The following are content-review requirements drawn from that supplied text;
they are not a finding that any current map meets them.

| Section / PDF page | Required content check | Implementation or review implication |
| --- | --- | --- |
| III–IV / 1 | National and administrative boundaries use the prescribed approved standard drawings. | A CN audience setting and approximate visual resemblance are insufficient evidence of an exact match. |
| V / 1 | Complete China maps depict the prescribed territorial extent and important islands. Land-border/coastline symbology determines requirements for the South China Sea segmented line and relevant East China Sea segments. Exceptions have conditions, including whether neighboring coastlines or boundaries are shown. | Check the actual style, extent and symbols; do not claim those lines are universally optional or mandatory in every map. |
| V(3) / 1 | Other displayed content must not obstruct important territorial features. | Inspect school pins, clusters, popups and controls at relevant scales; do not assume marker overlays are harmless to the depiction. |
| VI / 1–2 | South China Sea maps have prescribed extents, inset titles, island-group and reef content, standard names, and context-dependent naming rules. Listed groups/features include 东沙、西沙、中沙、南沙、曾母暗沙 and 黄岩岛. Some requirements vary by map type and scale. | Review both wide views and detailed views. Where applicable, the document requires 黄岩岛 to include 民主礁 in parentheses at scales larger than 1:4,000,000. Do not apply the same suffix or inset rule blindly to every interactive viewport. |
| VII / 2 | Diaoyu and associated islands are shown when within the map extent at scales larger than 1:100,000,000. There are exceptions for smaller-scale maps and maps without boundaries or territorial extents. | Verify island geometry and zoom-dependent visibility; a mainland screenshot cannot verify this. |
| VIII / 2 | Taiwan is represented as a provincial administrative unit. Taipei is a provincial administrative center; New Taipei, Taoyuan, Taichung, Tainan and Kaohsiung use prefecture-level administrative-center treatment. Taiwan Province maps include Diaoyu and Chiwei, with a stated exception for maps titled Taiwan Island. | Review administrative classification, city symbols, extent and labels, not only the word 台湾. The section does not itself mean every label must literally spell 台湾省 at every zoom. |
| IX / 2–3 | Hong Kong and Macao have provincial-level treatment, prescribed boundary references, and full-name/short-name rules that depend on scale. | Review their data classification, symbols, names and boundary visibility separately. |
| X–XV / 3 | International boundary references, uncertain island attribution, Kashmir depiction, place names, specified parenthetical names and the Changbaishan lake label have further requirements. Some naming rules exempt foreign-language and pinyin maps. | Inspect Kashmir's region boundary, ceasefire line, administrative/control-area labels, legend and coloring where applicable; CN alone has not verified these details. Avoid inventing island ownership or applying Chinese-language naming rules to every language indiscriminately. |

For interactive maps, printed scale thresholds must be assessed against the
rendered view, latitude and display scale; a fixed zoom number is not a universal
equivalent of a printed representative fraction. Preserve a record of the view
used for each check.

The PDF also contains requirements outside the current boundary-focused scope:
sections XIX–XXII address precision, restricted content and attributes, and a
0.5-metre limit on the ground resolution of imagery depicting areas within China.
These are recorded separately; they have not been implemented or verified for
the current imagery provider. Section XXIII states a five-year validity period
from issuance and supersedes the specified 2003 and 2009 content rules.

**Updated assessment:** the previous visual inspection establishes only the
presence of certain large-scale territorial markings. It does not establish
conformity with these detailed administrative, island, labeling, legend and
scale-dependent requirements. Mapbox remains unverified for this acceptance
target; neither the website nor the external demo is certified by this review.

## Integration acceptance steps

1. Explicitly set `worldview: 'CN'` rather than relying on a visitor's locale.
2. Use `language: 'en'` globally, as requested in the subsequent language
   correction. Inspect actual labels independently of the CN worldview; Mapbox
   falls back to local names where English translations are unavailable.
3. Verify Taiwan, 藏南, Aksai Chin, Diaoyu Dao / Chiwei Yu, and all South China Sea
   island groups and maritime segments at suitable regional and detail zooms.
4. Repeat the content review for every offered style, including Hybrid, and
   confirm the settings survive layer and globe/flat changes. Keep a persistent
   boundary/annotation overlay if a satellite-only style omits required content.
5. Record discrepancies and resolve them with the map provider or an authorized
   reference-data source before describing the map as matching the reference.
6. Do not reuse the reference image's review number as the site's own approval.

Mapbox documents the separate language/worldview settings and label fallbacks:
<https://docs.mapbox.com/help/dive-deeper/maps-internationalization/>.

## Closer Mapbox inspection and provider evidence

Additional review on 2026-10-15 used the same official Mapbox Standard demo,
with China (CN) visibly active. That review did not change the application.
It inspected rendered content through the demo's pan/zoom controls, without
copying its example access token or reading internal map feature objects.

| Detail | Direct observation | Limit of finding |
| --- | --- | --- |
| Taiwan / Diaoyu / Chiwei | Around zoom 5.4, 台湾, 臺北市, 钓鱼岛 and 赤尾屿 are visible, as are the maritime segments east and south of Taiwan. At the next closer view 黄尾屿 and 赤尾屿 are also visible. | Confirms these named features are displayed; does not verify all island outlines or Taiwan's underlying administrative classification. |
| Taipei and other Taiwanese cities | Taipei has a concentric-circle symbol, while Taichung and Kaohsiung use different city symbols in the inspected view. | A visual distinction exists; complete administrative-center treatment remains unverified. |
| Spratly group | At center approximately 113.018 E, 11.198 N, zoom 6.39, 南沙群岛 is labeled and a maritime segment is visible to the west. | Does not establish every reef name or the complete southern extent. |
| Zhongsha / Huangyan | At center approximately 116.556 E, 14.993 N, zoom 6.39, 中沙群岛 and 黄岩岛（民主礁） are visible beside the eastern maritime segment. | The parenthetical name is present. No universal conversion from zoom to the PDF's printed scale threshold is asserted. |
| Remaining detailed checks | Exact official boundary geometry, all named island groups and 曾母暗沙, Hong Kong/Macao administrative treatment, Kashmir line/legend/control-area treatment, and every relevant naming rule are not fully verified. | No full conformity conclusion. Hybrid and satellite styles were not covered by this Standard-demo inspection. |

Screenshots are saved in the task's visualization directory as
`mapbox-cn-taiwan-diaoyu-detail.jpg`, `mapbox-cn-spratly-detail.jpg`, and
`mapbox-cn-huangyan-detail.jpg`.

### Mapbox's express limitation

The current first-party [Mapbox Streets v8 worldview reference](https://docs.mapbox.com/data/tilesets/reference/mapbox-streets-v8/#worldview-text)
describes CN as features for a mainland Chinese audience, but **“not officially
approved for use in the PRC.”** It also states that worldview-generated displays
do not necessarily reflect government policy or have government approval.
This is stronger evidence than assuming that a CN selector certifies conformity.
It does not by itself establish that every visible boundary is wrong; conversely,
the positive visual checks above do not establish approval or complete adherence
to the supplied 2023 content standard.

### Alternatives with published evidence

The list below distinguishes evidence for an approved basemap from a blanket
claim about every product, style or modified school-map output. It is not an
exhaustive registry of all eligible providers.

| Provider / service | Published evidence | Qualification |
| --- | --- | --- |
| 天地图, including national and provincial services | [Changning planning/natural-resources government guidance](https://www.shcn.gov.cn/col7696/20220829/1220941.html) expressly recommends its online maps and APIs. [Guangdong's official node](https://guangdong.tianditu.gov.cn/) displays GS（2025）1508号 and offers vector, imagery, terrain and boundary resources. | Use the review number and terms for the actual national/provincial layer selected, rather than transferring a node's number to another product. |
| 高德 Amap | Its [developer compliance guide](https://developer.amap.com/api/compliance-center/check-and-reference/compliance), updated 2025-12-03, explicitly names 公开地图内容表示规范 and the territorial extent, administrative boundary, important-island and review-number requirements. It states Class A internet-mapping qualification. | Direct first-party discussion of the requested standard; developers still must use and preserve the approved content correctly. |
| 百度 Baidu Maps | [Compliance handbook](https://lbsyun.baidu.com/docs/pcsa?title=compliance/openguide) states Class A qualification. Its [official platform](https://lbs.baidu.com/) displays GS(2025)4125. [Customization terms](https://lbsyun.baidu.com/index.php?title=open/mapVisAgm) specifically explain that the standard review number covers its default basemap, and cannot be reused for modified standard-map content. | Strong default-basemap evidence; custom output is not automatically approved. |
| 中科星图 GEOVIS Earth / 星图云 | Its [map API product page](https://www.geovisearth.com/product/map) explicitly says its data is reviewed and published through the national map review center. It lists imagery GS（2026）3166号 / GS（2025）3131号 and electronic map GS（2025）3255号, with separate imagery-annotation and boundary resources. | Strong product-specific evidence. The page advertises imagery at 0.5 m within China / 2 m globally. Confirm which imagery version and annotation service are covered before integration. |
| 腾讯 Tencent Maps | The [government guidance](https://www.shcn.gov.cn/col7696/20220829/1220941.html) explicitly names Tencent among legal commercial map resources with review numbers. Its [location platform](https://lbs.qq.com/) offers web maps and search. | Government guidance is dated 2022, before the supplied 2023 norm. A current review number and the precise web/hybrid product remain to be checked. Its mobile SDK privacy-compliance guide is not evidence of boundary conformity. |
| 四维 NavInfo | The same government guidance explicitly names 四维. Its [current location-service platform](https://lbs.navinfo.com/) documents JavaScript maps, standard/satellite layers and search. | Current product-specific map approval remains to be checked; automotive high-definition map approvals are not proof for the web product. |
| 吉林一号 / 长光卫星 | The same government guidance explicitly names 吉林一号. Its [official platform agreement](https://www.jl1mall.com/openPlatform/serviceAgreement), especially section 10, discusses lawful basemap resources, national-boundary integrity, review-number preservation and overseas-use requirements. | Candidate for approved imagery services; do not treat satellite imagery alone as a verified territory/label layer. Current selected-product approval and overseas-use permission remain to be checked. |
| 自然资源部标准地图服务 | The [official service](https://bzdt.tianditu.gov.cn/) explicitly says its standard maps follow Chinese and international boundary-drawing standards. Direct use requires its review number; edited content requires review. | A strong reference/download source, not a replacement interactive world-map API. |

Do not describe Google, Apple, Bing, Esri, OpenStreetMap/OpenFreeMap, or an
unverified Mapbox CN style as satisfying this acceptance target merely because
they offer maps or satellite imagery. This review found no sufficient current
first-party assurance for those exact products. Rendering engines such as
MapLibre, Cesium and SuperMap do not determine conformity independently of the
basemap data and style loaded into them.

For this application's next evaluation, prioritize TianDiTu and GEOVIS's
approved imagery plus the corresponding boundary/annotation service; Amap and
Baidu are also well-documented alternatives. This is a product shortlist, not
confirmation that the school's eventual customized output is approved.

## Selected implementation

The user subsequently chose Mapbox's CN worldview and provided their own public
browser token. The frontend now uses Mapbox GL JS 3.32.0 with the worldview fixed
to CN and label language English (`en`). Street imports Mapbox Standard; Hybrid and
Satellite import Standard Satellite. Hybrid remains the default on every map
mount. Satellite hides roads and POIs but keeps place names and administrative
boundaries. The same component serves the public map and school-location picker.
Style changes reuse the Map instance and projection changes use globe/mercator.
The previous Esri/OpenFreeMap combination is no longer used by this component.

The token belongs in ignored frontend/.env.local or the deployment's frontend
build environment as VITE_MAPBOX_ACCESS_TOKEN; no token is recorded in this
document. Mapbox's native attribution is retained. This choice does not convert
the earlier limited visual inspection into a finding of official approval or
full conformity. User authorization covers implementing the chosen worldview,
not an assertion that Mapbox has obtained PRC map approval.

CN is a source-code constant, with no worldview selector, environment override,
query-string override, browser preference or admin setting. It is passed when
constructing the map and reapplied on every style load. Changing globe/flat mode
or any of the three basemaps does not change it.

The user's subsequent language correction overrides the earlier Chinese-label
choice: the shared map now requests English globally, independently of CN
worldview, both at construction and on each style load. This applies to globe,
flat map, all three basemaps, and school-location pickers. Controls and scale
remain English. Mapbox falls back to a feature's local name when no English name
exists; it does not globally force Chinese. See Mapbox's
[language and worldview documentation](https://docs.mapbox.com/help/dive-deeper/maps-internationalization/).
The earlier Chinese-label demo observations above remain historical; changing
the language does not change or certify the provider's boundary geometry.

Validation: 11 map unit tests, focused frontend lint, and the production build
pass. The isolated browser preview successfully loaded the supplied account's
satellite imagery at SAC, retained the selected school/camera across Satellite,
Street and Hybrid changes, and rendered the globe after switching from flat
mode. Testing used temporary databases with email delivery blocked. No Mapbox
billing settings or payment method were changed, and nothing was deployed.

Language-update validation: 13 map tests, focused source lint, and the production
build pass. The isolated browser preview rendered English labels on the Hybrid
globe, Street flat map, and Satellite globe after switching styles/projections.
English search, controls, scale, and attribution remain in place, and outgoing
Street View links now request English too. Boundary constants, native boundary
layers, school markers, and saved geographic locations were not changed.
