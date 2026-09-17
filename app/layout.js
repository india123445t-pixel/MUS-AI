import './globals.css';
import './workspace.css';

export const metadata={
  title:'AQLEVON AI',
  description:'AQLEVON AI — Learn · Create · Evolve',
  applicationName:'AQLEVON AI',
  manifest:'/api/status?manifest=1',
  icons:{icon:'/icon.svg',apple:'/icon.svg'},
  appleWebApp:{capable:true,statusBarStyle:'black-translucent',title:'AQLEVON AI'},
  formatDetection:{telephone:false}
};
export const viewport={themeColor:'#101014',colorScheme:'dark light',viewportFit:'cover',width:'device-width',initialScale:1,maximumScale:1};
export default function Layout({children}){return <html lang="ar" dir="rtl"><body>{children}</body></html>}
