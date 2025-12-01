import React from 'react';
import { BrowserRouter as Router, Routes, Route } from 'react-router-dom';
import NavBar from './components/NavBar';
import Landing from './pages/Landing';
import Login from './pages/Login';
import Register from './pages/Register';
import Home from './pages/Home';
import Tasks from './pages/Tasks';
import Profile from './pages/user/Profile';
import ManageUsers from './pages/admin/ManageUsers';
import { setupAccessTokenAutoRefresh, refreshAccessTokenIfNeeded } from './utils/auth';
import './App.css';
import SideNav from './components/SideNav';

function App() {
  React.useEffect(() => {
    setupAccessTokenAutoRefresh();
    refreshAccessTokenIfNeeded();
  }, []);

  return (
    <Router>
      <NavBar />
      <div style={{ display: 'flex' }}>
        <SideNav selected={window.location.pathname.startsWith('/admin/users') ? 'manageusers' : undefined} />
        <div style={{ flex: 1 }}>
          <Routes>
            <Route path="/" element={<Landing />} />
            <Route path="/login" element={<Login />} />
            <Route path="/register" element={<Register />} />
            <Route path="/home" element={<Home />} />
            <Route path="/tasks" element={<Tasks />} />
            <Route path="/users/profile" element={<Profile />} />
            <Route path="/admin/users" element={<ManageUsers />} />
          </Routes>
        </div>
      </div>
    </Router>
  );
}

export default App;
