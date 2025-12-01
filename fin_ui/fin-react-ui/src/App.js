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
import UserLayout from './components/UserLayout';

function App() {
  React.useEffect(() => {
    setupAccessTokenAutoRefresh();
    refreshAccessTokenIfNeeded();
  }, []);

  return (
    <Router>
      <NavBar />
      <Routes>
        <Route path="/" element={<Landing />} />
        <Route path="/login" element={<Login />} />
        <Route path="/register" element={<Register />} />
        <Route path="/home" element={<UserLayout><Home /></UserLayout>} />
        <Route path="/tasks" element={<UserLayout><Tasks /></UserLayout>} />
        <Route path="/users/profile" element={<UserLayout><Profile /></UserLayout>} />
        <Route path="/admin/users" element={<UserLayout><ManageUsers /></UserLayout>} />
      </Routes>
    </Router>
  );
}

export default App;
