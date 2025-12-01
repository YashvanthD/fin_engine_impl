import React from 'react';
import SideNav from './SideNav';
import { Box, Container } from '@mui/material';

const drawerWidth = 220;
const topNavHeight = 64; // AppBar fixed height

export default function UserLayout({ children }) {
  return (
    <>
      {/* Sticky SideNav below TopNavBar */}
      <Box sx={{ position: 'fixed', top: `${topNavHeight}px`, left: 0, width: drawerWidth, height: `calc(100vh - ${topNavHeight}px)`, zIndex: 1200, bgcolor: 'background.paper', boxShadow: 1 }}>
        <SideNav />
      </Box>
      {/* Main content area with smooth scrolling */}
      <Box sx={{ ml: `${drawerWidth}px`, pt: `${topNavHeight}px`, height: `calc(100vh - ${topNavHeight}px)`, overflowY: 'auto', scrollBehavior: 'smooth', bgcolor: '#f7f7f7' }}>
        <Container maxWidth="lg">
          {children}
        </Container>
      </Box>
    </>
  );
}
