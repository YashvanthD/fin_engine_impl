import React from 'react';
import SideNav from '../components/SideNav';


export default function Layout({ children, selectedNav, user, onProfileClick }) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100vh' }}>
      <TopNavBar user={user} onProfileClick={onProfileClick} />
      <div style={{ display: 'flex', flexGrow: 1, minHeight: 0 }}>
        <SideNav selected={selectedNav || 'home'} />
        <main style={{ flexGrow: 1, paddingLeft: 220, height: '100%', overflow: 'auto', background: '#fafafa', scrollBehavior: 'smooth', display: 'flex', justifyContent: 'center', alignItems: 'flex-start', width: '100%' }}>
          <div style={{ width: '100%', maxWidth: '1200px' }}>
            {children}
          </div>
        </main>
      </div>
    </div>
  );
}
