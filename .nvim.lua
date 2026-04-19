local venv = vim.fn.getcwd() .. "/.venv"
if vim.fn.isdirectory(venv) == 1 then
  vim.env.VIRTUAL_ENV = venv
  vim.env.PATH = venv .. "/bin:" .. vim.env.PATH
end
