import React, { useEffect, useState } from 'react';
import {
  Paper, Typography, Button, Dialog, DialogTitle, DialogContent, DialogActions,
  TextField, MenuItem, Select, InputLabel, FormControl, Stack, Chip, Grid, InputAdornment, IconButton,
  CircularProgress
} from '@mui/material';
import SearchIcon from '@mui/icons-material/Search';
import EditIcon from '@mui/icons-material/Edit';
import { apiFetch } from '../utils/api';
import { getUserInfo } from '../utils/auth';
import { fetchAccountUsers } from '../utils/userApi';
import { getDefaultEndDate, getTimeLeft } from '../utils/date';
import UserLayout from '../components/UserLayout';

const initialForm = {
  title: '',
  description: '',
  status: 'pending',
  priority: 3,
  assigned_to: '',
  end_date: getDefaultEndDate(),
  task_date: '',
  notes: '',
};

function getPriorityStyle(priority, status) {
  if (status === 'completed') {
    return { border: '1.5px solid #4caf50', boxShadow: '0 0 4px #4caf50' };
  }
  switch (priority) {
    case 1: return { border: '1.5px solid #f44336', boxShadow: '0 0 4px #f44336' };
    case 2: return { border: '1.5px solid #ff7961', boxShadow: '0 0 4px #ff7961' };
    case 3: return { border: '1.5px solid #ff9800', boxShadow: '0 0 4px #ff9800' };
    case 4: return { border: '1.5px solid #ffeb3b', boxShadow: '0 0 4px #ffeb3b' };
    case 5: return { border: '1.5px solid #4caf50', boxShadow: '0 0 4px #4caf50' };
    default: return { border: '1px solid #e0e0e0' };
  }
}

export default function Tasks() {
  const [tasks, setTasks] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [refresh, setRefresh] = useState(false);
  const [searchTerm, setSearchTerm] = useState('');
  const [filterStatus, setFilterStatus] = useState('all');
  const [dialogOpen, setDialogOpen] = useState(false);
  const [form, setForm] = useState(initialForm);
  const [formError, setFormError] = useState('');
  const [userOptions, setUserOptions] = useState([]);
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);
  const [taskToDelete, setTaskToDelete] = useState(null);
  const userInfo = getUserInfo();

  useEffect(() => {
    async function fetchTasks() {
      setLoading(true);
      setError('');
      try {
        const res = await apiFetch('/task/', { method: 'GET' });
        const data = await res.json();
        if (res.ok && data.success) {
          setTasks(data.tasks || []);
        } else {
          setError(data.error || 'Failed to fetch tasks');
        }
      } catch (err) {
        setError('Network/server error');
      }
      setLoading(false);
    }
    fetchTasks();
  }, [refresh]);

  useEffect(() => {
    async function loadUsers() {
      const users = await fetchAccountUsers();
      const selfUser = userInfo ? { user_key: userInfo.user_key, username: userInfo.user?.username || 'Self (You)' } : null;
      let options = users.filter(u => u.user_key !== selfUser?.user_key);
      if (selfUser) options = [selfUser, ...options];
      setUserOptions(options);
      // Set self as default assigned_to if creating new task
      if (!form.assigned_to && selfUser) {
        setForm(f => ({ ...f, assigned_to: selfUser.user_key }));
      }
    }
    loadUsers();
  }, [dialogOpen]);

  // Stats
  const meta = tasks.reduce((acc, t) => {
    if (t.status === 'completed') acc.completed++;
    else if (t.status === 'inprogress') acc.inprogress++;
    else acc.pending++;
    acc.total++;
    return acc;
  }, { completed: 0, inprogress: 0, pending: 0, total: 0 });

  // Filter/search and sort
  const filteredTasks = tasks.filter(t => {
    const matchesStatus = filterStatus === 'all' || t.status === filterStatus;
    const matchesSearch =
      !searchTerm ||
      (t.task_id && t.task_id.includes(searchTerm)) ||
      (t.title && t.title.toLowerCase().includes(searchTerm.toLowerCase())) ||
      (t.description && t.description.toLowerCase().includes(searchTerm.toLowerCase()));
    // Show completed tasks if searching or filtering for completed
    if (t.status === 'completed' && t.end_date) {
      const now = new Date();
      let end = new Date(t.end_date.replace(' ', 'T'));
      if ((now - end) > 3600000 && !searchTerm && filterStatus !== 'completed') return false;
    }
    return matchesStatus && matchesSearch;
  })
  // Move resolved (completed) tasks to end
  .sort((a, b) => {
    if (a.status === 'completed' && b.status !== 'completed') return 1;
    if (b.status === 'completed' && a.status !== 'completed') return -1;
    return 0;
  });

  // Form handlers
  function handleFormChange(e) {
    setForm({ ...form, [e.target.name]: e.target.value });
  }
  function handleFormSubmit(e) {
    e.preventDefault();
    setFormError('');
    let submitForm = { ...form };
    // Always set assigned_to to self if not set
    if (!submitForm.assigned_to && userInfo?.user_key) {
      submitForm.assigned_to = userInfo.user_key;
    }
    if (!submitForm.title || !submitForm.assigned_to || !submitForm.end_date) {
      setFormError('Fields marked * are required');
      return;
    }
    const isEdit = !!submitForm.task_id;
    const url = isEdit ? `/task/${submitForm.task_id}` : '/task/';
    const method = isEdit ? 'PUT' : 'POST';
    delete submitForm._id;
    apiFetch(url, {
      method,
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(submitForm)
    })
      .then(res => res.json())
      .then(data => {
        if (data.success) {
          setDialogOpen(false);
          setForm(initialForm);
          setRefresh(r => !r);
        } else {
          setFormError(data.error || (isEdit ? 'Failed to update task' : 'Failed to create task'));
        }
      })
      .catch((err) => setFormError('Network/server error: ' + err));
  }

  // Edit (future: open dialog with task data)
  function handleEdit(task) {
    setForm({
      ...task,
      title: task.title,
      description: task.description,
      status: task.status,
      priority: task.priority || 3,
      assigned_to: task.assigned_to,
      end_date: task.end_date || getDefaultEndDate(),
      task_date: task.task_date || '',
      notes: task.notes || '',
      task_id: task.task_id // Track for edit
    });
    setDialogOpen(true);
  }

  async function handleConfirmDelete() {
    if (!taskToDelete) return;
    try {
      await apiFetch(`/task/${taskToDelete.task_id}`, {
        method: 'DELETE',
      });
      setDeleteDialogOpen(false);
      setTaskToDelete(null);
      setRefresh(r => !r);
    } catch (err) {
      setError('Failed to delete task');
      setDeleteDialogOpen(false);
      setTaskToDelete(null);
    }
  }

  function handleCancelDelete() {
    setDeleteDialogOpen(false);
    setTaskToDelete(null);
  }

  function getPriorityLabel(priority) {
    switch(priority) {
      case 1: return 'High';
      case 2: return 'Critical';
      case 3: return 'Medium';
      case 4: return 'Low';
      case 5: return 'Normal';
      default: return 'Unknown';
    }
  }
  function getPriorityColor(priority) {
    switch(priority) {
      case 1: return 'error';
      case 2: return 'warning';
      case 3: return 'info';
      case 4: return 'success';
      case 5: return 'default';
      default: return 'default';
    }
  }
  function getUsername(userKey) {
    const user = userOptions.find(u => u.user_key === userKey);
    return user ? user.username : userKey;
  }
  function getNextAction(status) {
    switch(status) {
      case 'pending': return 'Start';
      case 'inprogress': return 'Resolve';
      case 'completed': return 'Resolved';
      case 'wontdo': return "Won't Do";
      default: return 'Next';
    }
  }
  function getNextActionColor(status) {
    switch(status) {
      case 'pending': return 'primary'; // blue
      case 'inprogress': return 'success'; // green
      case 'completed': return 'success'; // green
      case 'wontdo': return 'warning'; // yellow
      case 'resolve': return 'orange'; // orange for resolve
      default: return 'default';
    }
  }
  function getNextActionVariant(status) {
    switch(status) {
      case 'pending': return 'contained';
      case 'inprogress': return 'contained';
      case 'completed': return 'contained';
      case 'wontdo': return 'contained';
      case 'resolve': return 'contained';
      default: return 'contained';
    }
  }

  function handleNextAction(task) {
    // Update status: pending -> inprogress, inprogress -> completed, completed -> no-op
    let nextStatus = task.status;
    if (task.status === 'pending') nextStatus = 'inprogress';
    else if (task.status === 'inprogress') nextStatus = 'completed';
    else return; // completed or other: no-op
    apiFetch(`/task/${task.task_id}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ ...task, status: nextStatus })
    })
      .then(res => res.json())
      .then(data => {
        if (data.success) setRefresh(r => !r);
      });
  }

  function handleDeleteFromDialog() {
    setTaskToDelete(form);
    setDeleteDialogOpen(true);
  }

  return (
    <UserLayout>
      <Paper sx={{padding:4, maxWidth:1000, margin:'40px auto'}}>
        {/* Top bar */}
        <Stack direction="row" alignItems="center" justifyContent="space-between" sx={{mb:3}}>
          <Stack direction="row" spacing={2} alignItems="center">
            <Chip label={`Total: ${meta.total}`} color="primary" />
            <Chip label={`Completed: ${meta.completed}`} color="success" />
            <Chip label={`In Progress: ${meta.inprogress}`} color="info" />
            <Chip label={`Pending: ${meta.pending}`} color="default" />
            <FormControl size="small" sx={{minWidth:120}}>
              <InputLabel>Status</InputLabel>
              <Select value={filterStatus} label="Status" onChange={e => setFilterStatus(e.target.value)} variant="outlined">
                <MenuItem value="all">All</MenuItem>
                <MenuItem value="pending">Pending</MenuItem>
                <MenuItem value="inprogress">In Progress</MenuItem>
                <MenuItem value="completed">Completed</MenuItem>
              </Select>
            </FormControl>
          </Stack>
          <Button variant="contained" color="primary" onClick={() => { setDialogOpen(true); setForm(initialForm); }}>
            Create New Task
          </Button>
        </Stack>
        {/* Search box */}
        <TextField
          label="Search Task by ID or Keyword"
          value={searchTerm}
          onChange={e => setSearchTerm(e.target.value)}
          fullWidth
          size="small"
          sx={{mb:3}}
          InputProps={{
            endAdornment: (
              <InputAdornment position="end">
                <SearchIcon />
              </InputAdornment>
            )
          }}
        />
        {/* Error */}
        {error && <Typography color="error" sx={{mb:2}}>{error}</Typography>}
        {/* Tasks list */}
        {loading ? (
          <Stack alignItems="center" sx={{mt:4, mb:4}}>
            <CircularProgress />
            <Typography variant="body2" sx={{mt:2}}>Loading tasks...</Typography>
          </Stack>
        ) : (
          <Grid container spacing={2}>
            {filteredTasks.map((task, idx) => (
              <Grid item xs={12} sm={6} md={4} key={task.task_id || idx}>
                <Paper elevation={3} sx={{p:2, mb:2, ...getPriorityStyle(task.priority, task.status)}}>
                  <Stack direction="row" alignItems="center" justifyContent="space-between">
                    <Typography variant="h6" sx={{fontWeight:'bold'}}>{task.title}</Typography>
                    <Stack direction="row" alignItems="center" spacing={1}>
                      <Chip label={getPriorityLabel(task.priority)} color={getPriorityColor(task.priority)} size="small" />
                      <IconButton onClick={() => handleEdit(task)}><EditIcon /></IconButton>
                    </Stack>
                  </Stack>
                  <Typography variant="body2" sx={{mb:1, color:'#888'}}>{task.description}</Typography>
                  <Stack spacing={0.5} sx={{mb:1}}>
                    <Typography variant="body2" sx={{color:'#555'}}>
                      <strong>End Date:</strong> {task.end_date}
                    </Typography>
                    <Typography variant="body2" sx={{color:'#555'}}>
                      <strong>Time Left:</strong> {getTimeLeft(task.end_date)}
                    </Typography>
                    <Typography variant="body2" sx={{color:'#555'}}>
                      <strong>Assigned To:</strong> {getUsername(task.assigned_to)}
                    </Typography>
                    {task.recurring && (
                      <Typography variant="body2" sx={{color:'#555'}}>
                        <strong>Recurring:</strong> {task.recurring}
                      </Typography>
                    )}
                    {task.tags && Array.isArray(task.tags) && task.tags.length > 0 && (
                      <Typography variant="body2" sx={{color:'#555'}}>
                        <strong>Tags:</strong> {task.tags.join(', ')}
                      </Typography>
                    )}
                    {task.type && (
                      <Typography variant="body2" sx={{color:'#555'}}>
                        <strong>Type:</strong> {task.type}
                      </Typography>
                    )}
                    {/* Extendable: add more fields here as needed */}
                  </Stack>
                  <Stack direction="row" alignItems="center" justifyContent="space-between" sx={{mt:1}}>
                    <Stack direction="row" spacing={1} alignItems="center">
                      <Button
                        variant={getNextActionVariant(task.status)}
                        size="small"
                        color={task.status === 'completed' ? 'success' : (task.status === 'inprogress' ? 'warning' : getNextActionColor(task.status))}
                        sx={task.status === 'inprogress' ? {backgroundColor: 'orange', color: 'white', '&:hover': {backgroundColor: '#ff9800'}} : (task.status === 'completed' ? {backgroundColor: '#4caf50', color: 'white', opacity: 1, pointerEvents: 'none'} : {})}
                        onClick={() => handleNextAction(task)}
                        disabled={task.status === 'completed'}
                      >
                        {getNextAction(task.status)}
                      </Button>
                      {task.status === 'completed' && (
                        <Button
                          variant="contained"
                          color="error"
                          size="small"
                          sx={{ml:1}}
                          onClick={() => { setTaskToDelete(task); setDeleteDialogOpen(true); }}
                        >
                          Delete
                        </Button>
                      )}
                    </Stack>
                    <Typography variant="caption" sx={{color:'#aaa'}}>{task.task_id}</Typography>
                  </Stack>
                </Paper>
              </Grid>
            ))}
          </Grid>
        )}
        {/* Create/Edit Task Dialog */}
        <Dialog open={dialogOpen} onClose={() => setDialogOpen(false)} maxWidth="sm" fullWidth>
          <DialogTitle>{form.title ? 'Edit Task' : 'Create Task'}</DialogTitle>
          <form onSubmit={handleFormSubmit}>
            <DialogContent>
              <Stack spacing={2}>
                <TextField label={<span>Title <span style={{color:'red'}}>*</span></span>} name="title" value={form.title} onChange={handleFormChange} required fullWidth />
                <TextField label="Description" name="description" value={form.description} onChange={handleFormChange} multiline rows={2} fullWidth />
                <FormControl fullWidth>
                  <InputLabel>Status</InputLabel>
                  <Select name="status" value={form.status} label="Status" onChange={handleFormChange} variant="outlined">
                    <MenuItem value="pending">Pending</MenuItem>
                    <MenuItem value="inprogress">In Progress</MenuItem>
                    <MenuItem value="completed">Completed</MenuItem>
                  </Select>
                </FormControl>
                <FormControl fullWidth>
                  <InputLabel>Priority</InputLabel>
                  <Select name="priority" value={form.priority} label="Priority" onChange={handleFormChange} variant="outlined">
                    <MenuItem value={1}>1</MenuItem>
                    <MenuItem value={2}>2</MenuItem>
                    <MenuItem value={3}>3</MenuItem>
                    <MenuItem value={4}>4</MenuItem>
                    <MenuItem value={5}>5</MenuItem>
                  </Select>
                </FormControl>
                <FormControl fullWidth>
                  <InputLabel>Assigned To *</InputLabel>
                  <Select name="assigned_to" value={form.assigned_to} label="Assigned To *" onChange={handleFormChange} variant="outlined" required>
                    {userOptions.map(u => (
                      <MenuItem key={u.user_key} value={u.user_key}>{u.username || u.user_key}{u.user_key === userInfo?.user_key ? ' (You)' : ''}</MenuItem>
                    ))}
                  </Select>
                </FormControl>
                <TextField label={<span>End Date (YYYY-MM-DD) <span style={{color:'red'}}>*</span></span>} name="end_date" value={form.end_date} onChange={handleFormChange} required fullWidth />
                <TextField label="Task Date (YYYY-MM-DD)" name="task_date" value={form.task_date} onChange={handleFormChange} fullWidth />
                <TextField label="Notes" name="notes" value={form.notes} onChange={handleFormChange} multiline rows={2} fullWidth />
                {formError && <Typography color="error">{formError}</Typography>}
              </Stack>
            </DialogContent>
            <DialogActions>
              {form.task_id && (
                <Button onClick={handleDeleteFromDialog} variant="contained" color="error" sx={{mr:'auto'}}>Delete</Button>
              )}
              <Button onClick={() => setDialogOpen(false)}>Cancel</Button>
              <Button type="submit" variant="contained" color="primary">{form.title ? 'Update' : 'Create'}</Button>
            </DialogActions>
          </form>
        </Dialog>
        {/* Delete Confirmation Dialog */}
        <Dialog open={deleteDialogOpen} onClose={handleCancelDelete}>
          <DialogTitle>Confirm Delete</DialogTitle>
          <DialogContent>
            <Typography>Are you sure you want to delete the task "{taskToDelete?.title}"?</Typography>
          </DialogContent>
          <DialogActions>
            <Button onClick={handleCancelDelete}>Cancel</Button>
            <Button onClick={handleConfirmDelete} color="error" variant="contained">Delete</Button>
          </DialogActions>
        </Dialog>
      </Paper>
    </UserLayout>
  );
}
