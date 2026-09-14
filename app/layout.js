import './globals.css';

export const metadata={
  title:'MUS AI',
  description:'MUS AI — Learn · Create · Evolve',
  applicationName:'MUS AI',
  manifest:'/api/status?manifest=1',
  icons:{icon:'/api/status?icon=1',apple:'/api/status?icon=1'},
  appleWebApp:{capable:true,statusBarStyle:'black-translucent',title:'MUS AI'},
  formatDetection:{telephone:false}
};
export const viewport={themeColor:'#07111f',colorScheme:'dark',viewportFit:'cover',width:'device-width',initialScale:1,maximumScale:1};
export default function Layout({children}){return <html lang="ar" dir="rtl"><body>{children}</body></html>}
