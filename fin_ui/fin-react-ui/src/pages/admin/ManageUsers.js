import React, { useState, useEffect } from 'react';
import {
  Card, CardContent, Typography, Button, Stack, Dialog, DialogTitle, DialogContent, DialogActions, IconButton, Table, TableBody, TableCell, TableContainer, TableHead, TableRow, Paper
} from '@mui/material';
import AddIcon from '@mui/icons-material/Add';
import EditIcon from '@mui/icons-material/Edit';
import DeleteIcon from '@mui/icons-material/Delete';
import AddUser from './AddUser';
import { getAccessToken, getUserInfo } from '../../utils/auth';
import { apiFetch } from '../../utils/api';

export default function ManageUsers() {
  const [users, setUsers] = useState([]);
  const [addOpen, setAddOpen] = useState(false);
  const [editOpen, setEditOpen] = useState(false);
  const [selectedUser, setSelectedUser] = useState(null);
  const [editError, setEditError] = useState('');
  const [deleteLoading, setDeleteLoading] = useState(false);
  const userInfo = getUserInfo();
  const accountKey = userInfo?.account_key || '';

  // Fetch users from backend on load
  useEffect(() => {
    async function fetchUsers() {
      try {
        const res = await apiFetch('/user/list', {
          method: 'GET',
          headers: {
            'Authorization': `Bearer ${getAccessToken()}`
          }
        });
        const data = await res.json();
        if (res.ok && data.success && Array.isArray(data.users)) {
          // Add a local id for React rendering if not present
          setUsers(data.users.map((u, idx) => ({ ...u, id: idx + 1 })));
        } else {
          setEditError(data.error || 'Failed to fetch users');
        }
      } catch (err) {
        setEditError('Network/server error');
      }
    }
    fetchUsers();
  }, []);

  // Add user handler (API call for real usage)
  const handleAddUser = async (newUser) => {
    try {
      const res = await apiFetch(`/auth/account/${accountKey}/signup`, {
        method: 'POST',
        body: JSON.stringify(newUser),
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${getAccessToken()}`
        }
      });
      const data = await res.json();
      if (res.ok && data.success) {
        setUsers([...users, { ...newUser, id: users.length + 1, user_key: data.user_key }]);
        setAddOpen(false);
      } else {
        setEditError(data.error || 'Failed to add user');
      }
    } catch (err) {
      setEditError('Network/server error');
    }
  };

  // Remove user handler (API call)
  const handleRemoveUser = async (id, user_key) => {
    setDeleteLoading(true);
    setEditError('');
    if (!user_key) {
      setEditError('User key is missing. Cannot delete user.');
      setDeleteLoading(false);
      return;
    }
    try {
      const res = await apiFetch(`/user/account/${accountKey}/user/${user_key}`, {
        method: 'DELETE',
        headers: {
          'Authorization': `Bearer ${getAccessToken()}`
        }
      });
      const data = await res.json();
      if (res.ok && data.success) {
        setUsers(users.filter(u => u.id !== id));
      } else {
        setEditError(data.error || 'Failed to delete user');
      }
    } catch (err) {
      setEditError('Network/server error');
    }
    setDeleteLoading(false);
  };

  // Update user handler
  const handleUpdateUser = (id) => {
    const user = users.find(u => u.id === id);
    setSelectedUser(user);
    setEditOpen(true);
    setEditError('');
  };

  // Edit user submit handler (API call)
  const handleEditUserSubmit = async (updatedUser) => {
    setEditError('');
    try {
      const res = await apiFetch(`/auth/account/${accountKey}/user/${selectedUser.user_key}`, {
        method: 'PUT',
        body: JSON.stringify(updatedUser),
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${getAccessToken()}`
        }
      });
      const data = await res.json();
      if (res.ok && data.success) {
        setUsers(users.map(u => u.id === selectedUser.id ? { ...u, ...updatedUser } : u));
        setEditOpen(false);
        setSelectedUser(null);
      } else {
        setEditError(data.error || 'Failed to update user');
      }
    } catch (err) {
      setEditError('Network/server error');
    }
  };

  return (
    <div style={{ paddingTop: '64px' }}>
      <Card sx={{ maxWidth: 900, m: '40px auto', p: 2 }}>
        <CardContent>
          <Stack direction="row" justifyContent="space-between" alignItems="center" mb={2}>
            <Typography variant="h5" fontWeight={700}>Manage Users</Typography>
            <Button variant="contained" startIcon={<AddIcon />} onClick={() => setAddOpen(true)}>
              Add User
            </Button>
          </Stack>
          <TableContainer component={Paper}>
            <Table>
              <TableHead>
                <TableRow>
                  <TableCell>Username</TableCell>
                  <TableCell>Email</TableCell>
                  <TableCell>Phone</TableCell>
                  <TableCell>Roles</TableCell>
                  <TableCell align="right">Actions</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {users.map(user => (
                  <TableRow key={user.id}>
                    <TableCell>{user.username}</TableCell>
                    <TableCell>{user.email}</TableCell>
                    <TableCell>{user.phone}</TableCell>
                    <TableCell>{user.roles.join(', ')}</TableCell>
                    <TableCell align="right">
                      <IconButton color="primary" onClick={() => handleUpdateUser(user.id)}><EditIcon /></IconButton>
                      <IconButton color="error" onClick={() => handleRemoveUser(user.id, user.user_key)} disabled={deleteLoading}><DeleteIcon /></IconButton>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </TableContainer>
          {editError && <Typography color="error" mt={2}>{editError}</Typography>}
        </CardContent>
      </Card>
      <Dialog open={addOpen} onClose={() => setAddOpen(false)} maxWidth="sm" fullWidth>
        <DialogTitle>Add User</DialogTitle>
        <DialogContent>
          <AddUser onSubmit={handleAddUser} isDialog />
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setAddOpen(false)}>Cancel</Button>
        </DialogActions>
      </Dialog>
      <Dialog open={editOpen} onClose={() => { setEditOpen(false); setSelectedUser(null); }} maxWidth="sm" fullWidth>
        <DialogTitle>Edit User</DialogTitle>
        <DialogContent>
          {selectedUser && (
            <AddUser
              onSubmit={handleEditUserSubmit}
              isDialog
              initialData={selectedUser}
            />
          )}
        </DialogContent>
        <DialogActions>
          <Button onClick={() => { setEditOpen(false); setSelectedUser(null); }}>Cancel</Button>
        </DialogActions>
      </Dialog>
    </div>
  );
}
