import React from 'react';
import { Drawer, List, ListItem, ListItemIcon, ListItemText } from '@mui/material';
import AssignmentIcon from '@mui/icons-material/Assignment';
import HomeIcon from '@mui/icons-material/Home';
import { Link } from 'react-router-dom';

const drawerWidth = 220;

export default function SideNav({ selected = 'tasks', onSelect }) {
  return (
    <Drawer
      variant="permanent"
      anchor="left"
      sx={{
        width: drawerWidth,
        flexShrink: 0,
        zIndex: 100,
        [`& .MuiDrawer-paper`]: {
          width: drawerWidth,
          boxSizing: 'border-box',
          background: '#f5f5f5',
          top: '64px', // start below TopNavBar
          height: 'calc(100% - 64px)', // fill remaining height
          borderRight: '1px solid #e0e0e0',
          boxShadow: 'none',
        },
      }}
    >
      <List>
        <ListItem button selected={selected === 'home'} onClick={() => onSelect && onSelect('home')} component={Link} to="/home">
          <ListItemIcon><HomeIcon color="primary" /></ListItemIcon>
          <ListItemText primary="Home" />
        </ListItem>
        <ListItem button selected={selected === 'tasks'} onClick={() => onSelect && onSelect('tasks')} component={Link} to="/tasks">
          <ListItemIcon><AssignmentIcon color="primary" /></ListItemIcon>
          <ListItemText primary="Tasks" />
        </ListItem>
        {/* Future: Add more nav items here */}
      </List>
    </Drawer>
  );
}
