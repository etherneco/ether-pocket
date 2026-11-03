"""One-time source refactor with exact old sections and balanced QML blocks."""
from pathlib import Path
ROOT=Path(__file__).resolve().parent.parent
def end_block(source,start):
    at=source.index('{',start);depth=0;quote=None;escaped=False;i=at
    while i<len(source):
        c=source[i]
        if quote:
            if escaped:escaped=False
            elif c=='\\':escaped=True
            elif c==quote:quote=None
        elif c in ['"',"'"]:quote=c
        elif source[i:i+2]=='//':
            i=source.find('\n',i)
            if i<0:raise ValueError('Unterminated comment')
        elif c=='{':depth+=1
        elif c=='}':
            depth-=1
            if depth==0:return i+1
        i+=1
    raise ValueError('Unbalanced source')
def replace_block(source,marker,replacement):
    start=source.index(marker);return source[:start]+replacement+source[end_block(source,start):]
if __name__=='__main__':
    for name in ['Experience.qml','Main.qml']:
        path=ROOT/'ethershell/qml'/name;source=path.read_text(encoding='utf-8')
        backup=ROOT/'evidence/settings2-source-baseline'/name;backup.parent.mkdir(exist_ok=True);backup.write_text(source,encoding='utf-8')
        experience=name=='Experience.qml'
        marker=('                ScrollView {clip:true\n                    ColumnLayout {width:parent.width;spacing:16\n                        Caption {text:"Appearance"}' if experience else '                Flickable {\n                    contentHeight: settingsColumn.height;')
        replacement='''                SettingsWorkspace {id:settingsWorkspace;onClosed:ROOT_HOME;onOpenMobile:section=>{ROOT_MOBILE;mobileSettings.navigate(section)};onOpenStore:ROOT_STORE;onKeyboardRequested:if(Core.preferences.autoKeyboard)root.keyboardVisible=true}'''.replace('ROOT_HOME','root.home("home")' if experience else 'root.page="home"').replace('ROOT_MOBILE','root.home("mobile")' if experience else 'root.page="mobile"').replace('ROOT_STORE','root.home("store")' if experience else 'root.page="store"')
        source=replace_block(source,marker,replacement)
        network='                ColumnLayout {\n                    Heading {text:"Network & Internet"}'
        source=replace_block(source,network,'                Item {} // Legacy route is normalized to the shared Settings workspace.')
        source=source.replace('MobileNetworkSettings {id:mobileSettings;tokens:theme;','MobileNetworkSettings {id:mobileSettings;').replace('MobileNetworkSettings {id:mobileSettings;tokens:mobileTheme;','MobileNetworkSettings {id:mobileSettings;')
        if experience:
            source=source.replace('function home(destination){page=homeLocked?"home":destination||"home";','function home(destination){if(destination==="network"){settingsWorkspace.go("network");destination="settings"}page=homeLocked?"home":destination||"home";')
            source=source.replace('        width:root.width/root.unit;height:root.height/root.unit;scale:root.unit;transformOrigin:Item.TopLeft','''        property bool settingsActive:root.page==="settings"||root.page==="network"||root.page==="mobile"
        property real contentScale:settingsActive?Math.max(1,(root.screen.name.indexOf("DSI")===0||(!DevelopmentDesktop&&!Pocket.external)?Math.min(root.screen.width,root.screen.height)/400:root.unit)):root.unit
        width:root.width/contentScale;height:root.height/contentScale;scale:contentScale;transformOrigin:Item.TopLeft''')
            source=source.replace('ColumnLayout {anchors.fill:parent;anchors.margins:22;spacing:18','ColumnLayout {anchors.fill:parent;anchors.margins:parent.settingsActive?0:22;spacing:parent.settingsActive?0:18')
            source=source.replace('            RowLayout {Layout.fillWidth:true\n                Heading {text:root.page', '            RowLayout {Layout.fillWidth:true;visible:root.page!=="settings"&&root.page!=="network"&&root.page!=="mobile"\n                Heading {text:root.page')
        else:
            source=source.replace('    property string query: ""','    onPageChanged:if(page==="network"){settingsWorkspace.go("network");page="settings"}\n    property string query: ""')
        path.write_text(source,encoding='utf-8')
